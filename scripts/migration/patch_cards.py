with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()

# I will replace these exact strings
content = content.replace(
'''            </div>
          </div>

          {/* Card 2: Accounts & Balances Table (Replaced Holdings) */}''', 
'''            </div>
          </Card>

          {/* Card 2: Accounts & Balances Table (Replaced Holdings) */}''')

content = content.replace(
'''          </div>
        </div>

        {/* RIGHT COLUMN: Net Worth Across Entities Donut & Full Year Snapshot (~32% width) */}''',
'''          </Card>
        </div>

        {/* RIGHT COLUMN: Net Worth Across Entities Donut & Full Year Snapshot (~32% width) */}''')

content = content.replace(
'''            </div>
          </div>

          {/* Card 2: Full Year Snapshot (Replaced Performance) */}''',
'''            </div>
          </Card>

          {/* Card 2: Full Year Snapshot (Replaced Performance) */}''')

content = content.replace(
'''          </div>
        </div>
      </div>

      {/* Benchmark Selector Modal */}''',
'''          </Card>
        </div>
      </div>

      {/* Benchmark Selector Modal */}''')

# Also add import for Card at the top
imports = 'import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";\n'
content = content.replace('import Link from "next/link";', imports + 'import Link from "next/link";')

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)
