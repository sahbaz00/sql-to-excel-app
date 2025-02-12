from flask import Flask, render_template, request, send_file
import openpyxl
from io import BytesIO
import re

app = Flask(__name__)


def sql_to_excel_table_columns(sql_query):
    try:
        # Preprocessing steps to clean the query
        query = re.sub(r'--.*', '', sql_query)  # Remove line comments
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)  # Remove block comments
        query = re.sub(r"'\w+'", '', query)  # Remove string literals
        query = re.sub(r'\bEXTRACT\s*\([^)]+\)', '', query, flags=re.IGNORECASE)

        # Extract CTE names to exclude them later
        cte_pattern = r"with\s+([a-zA-Z0-9_]+)\s+as\s*\("
        ctes = set(re.findall(cte_pattern, query, re.IGNORECASE))

        # Identify physical tables (schema.table) from FROM/JOIN clauses
        table_pattern = r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_.]+)\b"
        candidates = re.findall(table_pattern, query, re.IGNORECASE)
        tables = sorted({
            c.lower()
            for c in candidates
            if '.' in c and c.lower() not in ctes
        })

        # Map table aliases to their physical tables
        alias_pattern = r'(?i)(?:FROM|JOIN)\s+([a-zA-Z0-9_.]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?'
        alias_map = {}
        for table, alias in re.findall(alias_pattern, query):
            table_lower = table.lower()
            if table_lower in tables:
                alias_lower = (alias or table.split('.')[-1]).lower()
                alias_map[alias_lower] = table_lower

        # Extract columns while ignoring aliases
        column_pattern = r'\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\b'
        column_dict = {t: set() for t in tables}

        for prefix, col in re.findall(column_pattern, query, re.IGNORECASE):
            table = alias_map.get(prefix.lower())
            if table and table in column_dict:
                column_dict[table].add(col.lower())

        # Convert sets to sorted lists
        for table in column_dict:
            column_dict[table] = sorted(column_dict[table])

        # Create an Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Table Columns"

        # Write data to the worksheet
        ws.append(["Table Name", "Column Name"])
        for table, columns in column_dict.items():
            for column in columns:
                ws.append([table, column])

        return wb

    except Exception as e:
        print(f"Error in sql_to_excel_table_columns: {e}")
        return None


def sql_to_excel_table_names(sql_query):
    try:
        # First remove all EXTRACT() function calls to avoid false positives
        query = re.sub(r'\bEXTRACT\s*\([^)]+\)', '', sql_query, flags=re.IGNORECASE)

        # Extract all CTE names
        cte_pattern = r"with\s+([a-zA-Z0-9_]+)\s+as\s*\("
        ctes = set(re.findall(cte_pattern, query, re.IGNORECASE))

        # Find all potential table references
        table_pattern = r"\b(?:from|join)\s+([a-zA-Z0-9_.]+)\b"
        candidates = re.findall(table_pattern, query, re.IGNORECASE)

        # Filter out CTEs and subquery aliases
        tables = set()
        for candidate in candidates:
            parts = candidate.split('.')
            if len(parts) > 1 and parts[0] not in ctes and candidate not in ctes:
                tables.add(candidate.lower())

        # Create an Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Table Names"

        # Write data to the worksheet
        ws.append(["Table Name"])
        for table in sorted(tables):
            ws.append([table])

        return wb

    except Exception as e:
        print(f"Error in sql_to_excel_table_names: {e}")
        return None


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        sql_query = request.form.get("sql_query")
        if not sql_query:
            return "No SQL query provided!", 400

        if "download_tables" in request.form:
            wb = sql_to_excel_table_names(sql_query)
            filename = "table_names.xlsx"
        elif "download_columns" in request.form:
            wb = sql_to_excel_table_columns(sql_query)
            filename = "table_columns.xlsx"
        else:
            return "Invalid action!", 400

        if not wb:
            return "Failed to generate Excel file. Check your SQL query.", 400

        # Save the workbook to a BytesIO object
        excel_file = BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        return send_file(excel_file, download_name=filename, as_attachment=True)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)