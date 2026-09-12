import json
from fastapi import FastAPI
from typing import Optional

def build_mcp_openapi_spec(server_url: Optional[str] = None) -> dict:
    from app.api.routers.mcp_router import router as mcp_router

    url = server_url or "https://lark-unvented-festivity.ngrok-free.dev"

    standalone_app = FastAPI(
        title="Greenline MCP & Portfolio API",
        description="Dedicated AI Agent and MCP API for Greenline Personal Finance. Strictly manages cashflow transactions, stock and investment trades, and category/account/asset catalogs.",
        version="1.0.0",
        servers=[
            {
                "url": url,
                "description": "Production Ngrok Gateway"
            }
        ]
    )

    standalone_app.include_router(mcp_router, prefix="/api/v1")
    spec = standalone_app.openapi()
    spec["openapi"] = "3.1.0"

    # Define Security Scheme
    if "components" not in spec:
        spec["components"] = {}

    spec["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "gl_mcp_...",
            "description": "Greenline API Key (gl_mcp_...) or Bearer JWT token."
        }
    }

    spec["security"] = [
        {
            "BearerAuth": []
        }
    ]

    # Operation map for clean operationId and friendly descriptions
    op_map = {
        ("/api/v1/mcp/categories", "get"): (
            "getCategories",
            "Fetch valid categories and accounts. AI MUST call this first to obtain category_id and valid account_name before recording expenses or income."
        ),
        ("/api/v1/mcp/cashflow", "get"): (
            "readCashflows",
            "Read cashflow statements with signed amounts (+ for income, - for expense) and filters by month (YYYY-MM), bank_account, category_id, or merchant."
        ),
        ("/api/v1/mcp/cashflow", "post"): (
            "mutateCashflows",
            "Bulk or single mutate cashflows (create, update, delete). Requires exact merchant, strict category_id, valid account_name, signed amounts, and balanced double-entry (sum of payments == sum of items)."
        ),
        ("/api/v1/mcp/stocks", "get"): (
            "readStockTransactions",
            "Fetch existing stocks, valid investment accounts, and recent transactions. AI MUST call this endpoint first before executing any buy/sell/dividend trade to look up valid account names, check if the asset already exists, and obtain asset_id or symbol."
        ),
        ("/api/v1/mcp/stocks", "post"): (
            "mutateStockTransactions",
            "Mutate stock transactions (buy, sell, dividend, bonus, split, deposit, withdrawal). AI MUST call GET /api/v1/mcp/stocks first to obtain exact account_name and check available_assets. If the asset does not exist in available_assets, set force_create_asset=true to create it automatically. Creating accounts is strictly forbidden."
        ),
    }

    # Filter paths to only our curated MCP routes (exclude openapi.json route itself)
    filtered_paths = {}
    for path, path_item in spec.get("paths", {}).items():
        if path.endswith("openapi.json"):
            continue
        filtered_paths[path] = path_item

        for method, op in path_item.items():
            if method.lower() in ["get", "post", "put", "delete"]:
                op["security"] = [{"BearerAuth": []}]

                # Clean parameters: remove X-API-Key and offset, remove required: false
                if "parameters" in op:
                    cleaned_params = []
                    for p in op["parameters"]:
                        p_name = p.get("name")
                        if p_name in ["X-API-Key", "offset"]:
                            continue

                        param_type = "string"
                        if "schema" in p:
                            if "anyOf" in p["schema"]:
                                non_null = [t for t in p["schema"]["anyOf"] if t.get("type") != "null"]
                                if non_null and "type" in non_null[0]:
                                    param_type = non_null[0]["type"]
                            elif "type" in p["schema"]:
                                param_type = p["schema"]["type"]

                        desc = p.get("description") or (p.get("schema", {}).get("description")) or ""
                        if p_name == "limit" and not desc:
                            desc = "Max number of statements to return (default 50)"

                        cleaned_params.append({
                            "name": p_name,
                            "in": "query",
                            "description": desc,
                            "schema": {
                                "type": param_type
                            }
                        })
                    op["parameters"] = cleaned_params

                # Ensure requestBody schema has no sibling fields alongside $ref
                if "requestBody" in op and "content" in op["requestBody"]:
                    for media_type, media_obj in op["requestBody"]["content"].items():
                        if "schema" in media_obj and "$ref" in media_obj["schema"]:
                            ref_val = media_obj["schema"]["$ref"]
                            media_obj["schema"] = {"$ref": ref_val}

                key = (path, method.lower())
                if key in op_map:
                    op_id, op_desc = op_map[key]
                    op["operationId"] = op_id
                    op["description"] = op_desc

    spec["paths"] = filtered_paths
    return spec
