# SQL River-Improved-Style Emitter (sql-rise)

A powerful SQL formatter that converts SQL queries into a clean, readable format with advanced features including comprehensive comment handling, CTE support, and sophisticated JOIN formatting.

## Features

- **Comment Handling**: Preserves and properly formats both line comments (`--`) and block comments
- **CTE (Common Table Expression) Support**: Advanced formatting with detailed indentation for WITH clauses
- **Window Function Support**: Proper formatting of OVER clauses and window functions
- **Complete Nested Indentation**: Handles nested CASE statements and subqueries with appropriate indentation
- **Comma-First Style**: SELECT items formatted in comma-first style for better readability
- **UNION/UNION ALL Support**: Proper formatting of UNION operations at the top level
- **Advanced JOIN Formatting**: 
  - JOIN clauses with ON conditions on the same line
  - Support for subqueries in JOIN clauses with proper `() ON` formatting
  - Extended JOIN types (INNER, LEFT OUTER, RIGHT OUTER, FULL OUTER, CROSS, etc.)
- **GROUP BY Formatting**: Comma-separated formatting for GROUP BY clauses
- **Standardized Indentation**: Consistent 4-space indentation for main clauses
- **Function Preservation**: Preserves function parentheses (e.g., `COUNT(...)`)
- **Keyword Spacing**: Automatic spacing for IN, LATERAL, EXISTS keywords

## Installation

No installation required. Simply download the `sql-rise.py` script.

## Usage

### Command Line

```bash
# Format SQL from standard input
echo "SELECT * FROM table WHERE id = 1" | python sql-rise.py

# Format SQL file
python sql-rise.py < input.sql > output.sql

# Show usage and examples
python sql-rise.py
```

### DBeaver Integration

1. Open DBeaver
2. Go to **Window** → **Preferences** (or **DBeaver** → **Preferences** on macOS)
3. Navigate to **Editors** → **SQL Editor** → **Formatting**
4. Select **External Formatter**
5. Set the command to: `python3 /path/to/sql-rise.py`
   - Use `which python3` to find your Python path
   - Replace `/path/to/` with the actual path to the script

## Examples

### Basic SELECT Statement

**Input:**
```sql
SELECT id,name,email FROM users WHERE active=1 AND created_at>'2023-01-01'
```

**Output:**
```sql
    SELECT id
         , name
         , email
      FROM users
     WHERE active = 1
       AND created_at > '2023-01-01'
           ;
```

### WITH Clause (CTE)

**Input:**
```sql
WITH user_stats AS (SELECT user_id, COUNT(*) as order_count FROM orders GROUP BY user_id), active_users AS (SELECT * FROM users WHERE active = 1) SELECT u.name, s.order_count FROM active_users u JOIN user_stats s ON u.id = s.user_id
```

**Output:**
```sql
    WITH user_stats AS (
  SELECT user_id
       , COUNT(*) as order_count
    FROM orders
GROUP BY user_id
         )

       , active_users AS (
  SELECT *
    FROM users
   WHERE active = 1
         )

  SELECT u.name
       , s.order_count
    FROM active_users u
    JOIN user_stats s ON u.id = s.user_id
         ;
```

### UNION Operations

**Input:**
```sql
SELECT id, name FROM customers UNION ALL SELECT id, company_name FROM suppliers ORDER BY name
```

**Output:**
```sql
    SELECT id
         , name
      FROM customers
 UNION ALL
    SELECT id
         , company_name
      FROM suppliers
  ORDER BY name
           ;
```

### Complex JOIN with Subqueries

**Input:**
```sql
SELECT * FROM orders o LEFT JOIN (SELECT customer_id, COUNT(*) as total_orders FROM orders GROUP BY customer_id) stats ON o.customer_id = stats.customer_id AND o.status = 'completed'
```

**Output:**
```sql
    SELECT *
      FROM orders o
 LEFT JOIN (
              SELECT customer_id
                   , COUNT(*) as total_orders
                FROM orders
            GROUP BY customer_id
           ) stats ON o.customer_id = stats.customer_id
       AND o.status = 'completed'
           ;
```

### CASE Statements

**Input:**
```sql
SELECT id, CASE WHEN status = 'active' THEN 'Active User' WHEN status = 'inactive' THEN 'Inactive User' ELSE 'Unknown' END as status_label FROM users
```

**Output:**
```sql
    SELECT id
         , CASE WHEN status = 'active'
                THEN 'Active User'
                WHEN status = 'inactive'
                THEN 'Inactive User'
                ELSE 'Unknown'
                 END AS status_label
      FROM users
           ;
```

## Formatting Rules

### Indentation
- Main clauses (SELECT, FROM, WHERE, etc.) use consistent 4-space base indentation
- Comma-first style for SELECT items with 9-space indentation for continuation
- Nested elements (CTEs, subqueries, CASE statements) use additional indentation

### Keywords
- All SQL keywords are converted to uppercase
- Function names preserve their case
- Automatic spacing added between keywords and parentheses (IN, LATERAL, EXISTS)

### Comments
- Line comments (`--`) are preserved and properly positioned
- Comments are maintained with original content

### JOIN Formatting
- JOIN type and table/subquery on same line as first ON condition
- Additional AND conditions on new lines with proper indentation
- Support for all JOIN types with consistent alignment

## Technical Details

### Dependencies
- Python 3.6+
- `sqlparse` library for SQL parsing
- `re` module for regular expressions

### Supported SQL Features
- SELECT, INSERT, UPDATE, DELETE statements
- WITH clauses (CTEs) with multiple definitions
- All JOIN types (INNER, LEFT, RIGHT, FULL, OUTER, CROSS)
- UNION and UNION ALL operations
- Window functions with OVER clauses
- CASE statements with WHEN/THEN/ELSE
- Subqueries in SELECT items and JOIN clauses
- GROUP BY, HAVING, ORDER BY, LIMIT clauses

### Limitations
- Designed primarily for DBeaver and standard SQL dialects
- Complex stored procedures may require manual adjustment
- Very large SQL files may experience performance limitations

## Contributing

This tool is designed to provide clean, readable SQL formatting with a focus on maintainability and consistency. Feel free to submit issues or improvements.

## License

MIT License - Feel free to use and modify as needed.