export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasMore: boolean;
}

export function parsePaginatedResponse<T>(res: any, defaultPage = 1, defaultPageSize = 20): PaginatedResult<T> {
  if (!res) {
    return { items: [], total: 0, page: defaultPage, pageSize: defaultPageSize, totalPages: 0, hasMore: false };
  }

  let items: T[] = [];
  if (Array.isArray(res.items)) {
    items = res.items;
  } else if (Array.isArray(res)) {
    items = [...res];
  } else if (res.items && typeof res.items === "object") {
    items = Object.values(res.items);
  }

  const total: number = typeof res.total === "number" ? res.total : items.length;
  const page: number = typeof res.page === "number" ? res.page : defaultPage;
  const pageSize: number = typeof res.page_size === "number" ? res.page_size : defaultPageSize;
  const totalPages: number = typeof res.total_pages === "number" ? res.total_pages : Math.ceil(total / pageSize);

  let hasMore = false;
  if (typeof res.has_more === "boolean") {
    hasMore = res.has_more;
  } else if (typeof res.has_next === "boolean") {
    hasMore = res.has_next;
  } else if (typeof res.total === "number" && typeof res.page === "number") {
    hasMore = page * pageSize < total;
  } else {
    hasMore = false;
  }

  return { items, total, page, pageSize, totalPages, hasMore };
}

export function syncUrlPage(targetPage: number) {
  if (typeof window === "undefined") return;
  try {
    const url = new URL(window.location.href);
    if (targetPage > 1) {
      url.searchParams.set("page", String(targetPage));
    } else {
      url.searchParams.delete("page");
    }
    const search = url.searchParams.toString();
    const newPath = `${url.pathname}${search ? `?${search}` : ""}${url.hash}`;
    window.history.replaceState(null, "", newPath);
  } catch (e) {
    console.error("Failed to sync URL page:", e);
  }
}
