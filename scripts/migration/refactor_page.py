import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# Add shadcn imports
imports = """import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
"""
content = content.replace('import Link from "next/link";', 'import Link from "next/link";\n' + imports)

# Refactor Net Worth Card
content = content.replace('<div className="getquin-card p-5">', '<Card className="p-5 shadow-sm">')
# Close cards (careful with this, I'll do it manually)
content = content.replace('          </div>\n\n          {/* Card 2', '          </Card>\n\n          {/* Card 2')
content = content.replace('          </div>\n\n          {/* Card 2: Full Year', '          </Card>\n\n          {/* Card 2: Full Year')
content = content.replace('          </div>\n        </div>\n\n        {/* RIGHT COLUMN', '          </Card>\n        </div>\n\n        {/* RIGHT COLUMN')
content = content.replace('          </div>\n        </div>\n      </div>\n\n      {/* Benchmark Selector Modal', '          </Card>\n        </div>\n      </div>\n\n      {/* Benchmark Selector Modal')

# Buttons
content = content.replace('className="btn-pill-black text-[11px]"', 'className="text-[11px]" variant="default" size="sm"')
content = content.replace('<Link href="/accounts" className="text-[11px]" variant="default" size="sm">', '<Link href="/accounts"><Button className="text-[11px]" size="sm">')
# Wait, replacing Link children is tricky.

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)
