import re

with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# Add imports
imports = """import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
"""
content = content.replace('import Link from "next/link";', 'import Link from "next/link";\n' + imports)

# Replace getquin-card with Card
content = content.replace('<div className="getquin-card p-5">', '<Card className="p-5">')
content = content.replace('<div className="getquin-card p-5">', '<Card className="p-5">')
content = content.replace('</Card>\n\n          {/* Card 2', '</Card>\n\n          {/* Card 2') # just checking logic
# Wait, replacing closing tags of getquin-card is hard via simple regex because it's just </div>
# I will use regex carefully.

# Let's just do a simpler sed-like regex approach.
# getquin-card is used in exactly 4 places (Net Worth Hero, Accounts & Balances, Entities Donut, Full Year Snapshot)
