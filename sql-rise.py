#!/usr/bin/env python3
"""
SQL River-Style Formatter - Unified Architecture
- Global river line calculation across all queries
- LEFT CLAUSE / RIGHT SENTENCE classification
- Primary and secondary river line support
"""

import sys
import re
from typing import List, Dict, Optional

class SQLToken:
    def __init__(self, token_type: str, content: str, line_num: int = 0):
        self.type = token_type  # 'LEFT_CLAUSE', 'RIGHT_SENTENCE', 'CONTINUATION', 'SEPARATOR'
        self.content = content
        self.line_num = line_num

class RiverFormatter:
    def __init__(self):
        self.primary_river_pos = 0
        self.secondary_river_pos = 0
        self.left_clauses = []
        self.secondary_clauses = []  # CASE, WHEN, THEN, ELSE, END for secondary river
        self.cte_structure = []  # Track CTE structure: [{'name': 'cte1', 'start_line': 1, 'end_line': 5}, ...]
        self.subquery_depth = 0  # Track nesting depth of subqueries
        
        # Extended LEFT CLAUSE patterns
        self.left_clause_patterns = [
            # Basic SQL clauses
            r'\bSELECT\s+DISTINCT\b', r'\bSELECT\b',
            r'\bFROM\b', r'\bWHERE\b', r'\bGROUP\s+BY\b', r'\bHAVING\b',
            r'\bORDER\s+BY\b', r'\bLIMIT\b',
            
            # JOIN types
            r'\bFULL\s+OUTER\s+JOIN\b', r'\bLEFT\s+OUTER\s+JOIN\b', r'\bRIGHT\s+OUTER\s+JOIN\b',
            r'\bINNER\s+JOIN\b', r'\bLEFT\s+JOIN\b', r'\bRIGHT\s+JOIN\b', r'\bFULL\s+JOIN\b',
            r'\bCROSS\s+JOIN\b', r'\bJOIN\b',
            
            # UNION types
            r'\bUNION\s+ALL\b', r'\bUNION\b',
            
            # CTE and structure
            r'\bWITH\b', r'\bAS\b',
            
            # DDL and DML
            r'\bCREATE\s+TEMP\s+TABLE\b', r'\bCREATE\s+TABLE\b',
            r'\bINSERT\s+INTO\b', r'\bUPDATE\b', r'\bSET\b', r'\bDELETE\b',
            
            # Comments
            r'--\s*,', r'--\s*\b(?:SELECT|FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|UNION|WITH|AS|INSERT\s+INTO|UPDATE|SET|DELETE|DECLARE|DO)\b', r'--',
            
            # Other
            r'\bDECLARE\b', r'\bDO\b',
        ]
        
        # Continuation patterns (special LEFT CLAUSE)
        self.continuation_patterns = [
            r'^\s*,\s*',  # Comma continuation
            r'^\s*AND\b', r'^\s*OR\b',  # Logical operators
        ]
        
        # Secondary river patterns (CASE statements)
        self.secondary_clause_patterns = [
            r'\bCASE\b', r'\bWHEN\b', r'\bTHEN\b', r'\bELSE\b', r'\bEND\b'
        ]
        
    def format_sql(self, sql: str) -> str:
        """Main entry point for SQL formatting"""
        if not sql.strip():
            return sql
            
        # Step 1: Analyze CTE structure
        self._analyze_cte_structure(sql)
        
        # Step 2: Global scan to find all LEFT CLAUSES
        self._extract_all_left_clauses(sql)
        
        # Step 3: Extract secondary clauses
        self._extract_secondary_clauses(sql)
        
        # Step 4: Calculate primary and secondary river line positions
        self._calculate_primary_river()
        self._calculate_secondary_river()
        
        # Step 5: Format the SQL
        formatted = self._format_with_river(sql)
        
        return formatted
    
    def _analyze_cte_structure(self, sql: str):
        """Analyze CTE structure to identify boundaries and nesting"""
        self.cte_structure = []
        
        # Remove comments for accurate analysis
        sql_clean = self._remove_comments(sql)
        # For single-line SQL with multiple CTEs, use regex to find CTE boundaries
        cte_pattern = r'\bWITH\s+(\w+)\s+AS\s*\([^)]*\)(?:\s*,\s*(\w+)\s+AS\s*\([^)]*\))*'
        
        # Find all CTE definitions
        cte_matches = list(re.finditer(r'(\w+)\s+AS\s*(\([^)]+\))', sql_clean, re.IGNORECASE))
        
        if cte_matches:
            for i, match in enumerate(cte_matches):
                cte_name = match.group(1).upper()
                cte_content = match.group(2)
                
                # Add CTE to structure
                self.cte_structure.append({
                    'name': cte_name,
                    'start_line': 1,  # All on same line for single-line SQL
                    'end_line': 1,
                    'has_parentheses': True
                })
            
            # Check if there's a main query after CTEs
            # Find the position after the last CTE
            if cte_matches:
                last_match = cte_matches[-1]
                remaining_sql = sql_clean[last_match.end():].strip()
                if re.search(r'\bSELECT\b', remaining_sql, re.IGNORECASE):
                    self.cte_structure.append({
                        'name': 'MAIN_QUERY',
                        'start_line': 1,
                        'end_line': 1,
                        'has_parentheses': False
                    })
    
    def _extract_all_left_clauses(self, sql: str):
        """Extract all LEFT CLAUSES from entire input to calculate global river"""
        self.left_clauses = []
        
        # First, find all LEFT CLAUSE patterns (including comments)
        for pattern in self.left_clause_patterns:
            matches = re.finditer(pattern, sql, re.IGNORECASE)
            for match in matches:
                clause = match.group().strip()
                # Normalize whitespace in multi-word clauses
                clause = ' '.join(clause.split())
                if clause not in self.left_clauses:
                    self.left_clauses.append(clause)
        
        # Also check for continuation commas and operators in each line
        lines = sql.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(','):
                self.left_clauses.append(',')
            elif line.startswith('AND ') or line.startswith('OR '):
                parts = line.split(None, 1)
                if parts:
                    self.left_clauses.append(parts[0])
            elif line.startswith('--'):
                # Check for comment patterns
                if re.match(r'^--\s*,', line):
                    comment_clause = '-- ,'
                    if comment_clause not in self.left_clauses:
                        self.left_clauses.append(comment_clause)
                elif re.match(r'^--\s*\b(?:SELECT|FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+OUTER\s+JOIN|LEFT\s+OUTER\s+JOIN|RIGHT\s+OUTER\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN|UNION\s+ALL|UNION|WITH|AS|CREATE\s+TEMP\s+TABLE|CREATE\s+TABLE|INSERT\s+INTO|UPDATE|SET|DELETE|DECLARE|DO)\b', line, re.IGNORECASE):
                    # Extract the comment + keyword as a clause
                    match = re.match(r'^--\s*(\b(?:SELECT|FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+OUTER\s+JOIN|LEFT\s+OUTER\s+JOIN|RIGHT\s+OUTER\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN|UNION\s+ALL|UNION|WITH|AS|CREATE\s+TEMP\s+TABLE|CREATE\s+TABLE|INSERT\s+INTO|UPDATE|SET|DELETE|DECLARE|DO)\b)', line, re.IGNORECASE)
                    if match:
                        keyword = match.group(1).upper()
                        comment_clause = f'-- {keyword}'
                        if comment_clause not in self.left_clauses:
                            self.left_clauses.append(comment_clause)
                else:
                    # Just comment
                    if '--' not in self.left_clauses:
                        self.left_clauses.append('--')
    
    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments for pattern matching"""
        # Remove line comments
        lines = sql.split('\n')
        clean_lines = []
        for line in lines:
            if '--' in line:
                line = line[:line.find('--')]
            clean_lines.append(line)
        return '\n'.join(clean_lines)
    
    def _calculate_primary_river(self):
        """Calculate primary river line position from all LEFT CLAUSES"""
        if not self.left_clauses:
            self.primary_river_pos = 7
            return
            
        max_clause_length = max(len(clause) for clause in self.left_clauses)
        self.primary_river_pos = 7 + max_clause_length
    
    def _extract_secondary_clauses(self, sql: str):
        """Extract secondary clauses for both CASE and subquery contexts"""
        self.secondary_clauses = []
        
        # For CASE statements: extract CASE WHEN as compound clause
        case_when_pattern = r'\bCASE\s+WHEN\b'
        case_when_matches = re.finditer(case_when_pattern, sql, re.IGNORECASE)
        for match in case_when_matches:
            clause = 'CASE WHEN'
            if clause not in self.secondary_clauses:
                self.secondary_clauses.append(clause)
        
        # For subqueries: extract SELECT and other SQL clauses within parentheses
        # This is a simplified approach - could be enhanced with proper parentheses parsing
        subquery_patterns = [r'\(\s*SELECT\b', r'\(\s*FROM\b', r'\(\s*WHERE\b']
        for pattern in subquery_patterns:
            matches = re.finditer(pattern, sql, re.IGNORECASE)
            for match in matches:
                # Extract the clause part (e.g., "SELECT" from "(SELECT")
                clause_match = re.search(r'\b(SELECT|FROM|WHERE)\b', match.group(), re.IGNORECASE)
                if clause_match:
                    clause = clause_match.group().upper()
                    if clause not in self.secondary_clauses:
                        self.secondary_clauses.append(clause)
        
        # Also add other secondary patterns
        for pattern in self.secondary_clause_patterns:
            matches = re.finditer(pattern, sql, re.IGNORECASE)
            for match in matches:
                clause = match.group().strip().upper()
                if clause not in self.secondary_clauses:
                    self.secondary_clauses.append(clause)
    
    def _calculate_secondary_river(self):
        """Calculate secondary river line position"""
        if not self.secondary_clauses:
            # Default: primary + 10 for CASE contexts (includes river space)
            self.secondary_river_pos = self.primary_river_pos + 10
            return
        
        # Find the maximum length of secondary clauses
        max_secondary_length = max(len(clause) for clause in self.secondary_clauses)
        
        # Check if we have CASE WHEN (CASE context)
        has_case_when = 'CASE WHEN' in self.secondary_clauses
        
        if has_case_when:
            # CASE context: primary + 1 (for primary river space) + 9 (gap) = primary + 10
            self.secondary_river_pos = self.primary_river_pos + 10
        else:
            # Subquery context: primary + 1 (for primary river space) + proper gap
            # For subqueries, use max secondary clause length + 3 margin + 1 for river space
            self.secondary_river_pos = self.primary_river_pos + max_secondary_length + 4
    
    def _format_with_river(self, sql: str) -> str:
        """Format SQL using calculated river line - preserve all original tokens"""
        # First, split by actual lines, then process each line for logical formatting
        input_lines = sql.split('\n')
        logical_lines = []
        
        for line in input_lines:
            if line.strip().startswith('--'):
                # Comment line - keep as is
                logical_lines.append(line.strip())
            else:
                # SQL line - split into logical parts
                sql_logical = self._split_into_logical_lines(line)
                logical_lines.extend(sql_logical)
        
        formatted_lines = []
        line_num = 0
        
        # Track parentheses context for subquery detection
        paren_depth = 0
        in_subquery = False
        
        i = 0
        while i < len(logical_lines):
            line_num += 1
            logical_line = logical_lines[i]
            
            if not logical_line.strip():
                formatted_lines.append('')
                i += 1
                continue
            
            # Check for WHEN THEN combination patterns
            current_upper = logical_line.strip().upper()
            
            # Debug output for combination logic (disabled)
            # if 'CASE' in current_upper or 'WHEN' in current_upper or 'THEN' in current_upper:
            #     print(f"DEBUG: Line {i}: {repr(logical_line)} -> {repr(current_upper)}")
            #     if i + 1 < len(logical_lines):
            #         next_upper = logical_lines[i + 1].strip().upper() 
            #         print(f"DEBUG: Next {i+1}: {repr(logical_lines[i + 1])} -> {repr(next_upper)}")
            
            # Pattern 1: WHEN ... followed by line starting with THEN
            if (current_upper.startswith('WHEN ') and 
                i + 1 < len(logical_lines) and 
                logical_lines[i + 1].strip().upper().startswith('THEN ')):
                
                # Combine WHEN and THEN into single line
                when_part = logical_line.strip()
                then_part = logical_lines[i + 1].strip()
                combined_line = f"{when_part} {then_part}"
                
                # Format the combined line
                formatted_line = self._format_case_clause(combined_line)
                formatted_lines.append(formatted_line)
                i += 2  # Skip both WHEN and THEN lines
                continue
            
            # Pattern 2: CASE WHEN followed by line starting with THEN (including comma-first)
            elif ((current_upper.startswith('CASE WHEN ') or current_upper.startswith(', CASE WHEN ')) and 
                  i + 1 < len(logical_lines) and 
                  logical_lines[i + 1].strip().upper().startswith('THEN ')):
                
                # Debug output (disabled)
                # print(f"DEBUG: Pattern 2 matched - {repr(logical_line)} + {repr(logical_lines[i + 1])}")
                
                # Combine CASE WHEN and THEN into single line
                case_when_part = logical_line.strip()
                then_part = logical_lines[i + 1].strip()
                combined_line = f"{case_when_part} {then_part}"
                
                # Format the combined line as CASE clause
                formatted_line = self._format_case_clause(combined_line)
                formatted_lines.append(formatted_line)
                i += 2  # Skip both CASE WHEN and THEN lines
                continue
            
            # Pattern 3: CASE WHEN (keywords only) followed by condition ending with THEN
            elif (current_upper == 'CASE WHEN' and 
                  i + 1 < len(logical_lines) and 
                  logical_lines[i + 1].strip().upper().endswith(' THEN')):
                
                # Combine CASE WHEN keywords with condition + THEN
                case_when_keywords = logical_line.strip()
                condition_then = logical_lines[i + 1].strip()
                combined_line = f"{case_when_keywords} {condition_then}"
                
                # Format the combined line as CASE clause  
                formatted_line = self._format_case_clause(combined_line)
                formatted_lines.append(formatted_line)
                i += 2  # Skip both lines
                continue
            
            # Pattern 4: WHEN (keyword only) followed by condition ending with THEN
            elif (current_upper == 'WHEN' and 
                  i + 1 < len(logical_lines) and 
                  logical_lines[i + 1].strip().upper().endswith(' THEN')):
                
                # Combine WHEN keyword with condition + THEN
                when_keyword = logical_line.strip()
                condition_then = logical_lines[i + 1].strip()
                combined_line = f"{when_keyword} {condition_then}"
                
                # Format the combined line as CASE clause
                formatted_line = self._format_case_clause(combined_line)
                formatted_lines.append(formatted_line)
                i += 2  # Skip both lines
                continue
            
            current_line = logical_line.strip()
            
            # Store current subquery context for formatting this line
            format_in_subquery = in_subquery
            
            # Update parentheses context tracking for next lines
            # Check for opening parentheses (including in combined lines like "FROM (")
            if '(' in current_line:
                paren_count = current_line.count('(')
                paren_depth += paren_count
                if paren_depth > 0:
                    in_subquery = True
            
            # Check for closing parentheses
            if ')' in current_line:
                paren_count = current_line.count(')')
                paren_depth -= paren_count
                if paren_depth <= 0:
                    in_subquery = False
                    paren_depth = 0  # Don't go negative
            
            # Check for closing parenthesis followed by semicolon pattern
            if (logical_line.strip() == ')' and 
                i + 1 < len(logical_lines) and 
                logical_lines[i + 1].strip() == ';'):
                
                # Combine ) and ; on the same line
                close_paren_pos = self.primary_river_pos + 1
                formatted_line = f"{' ' * close_paren_pos});"
                formatted_lines.append(formatted_line)
                i += 2  # Skip both ) and ; lines
                continue
            
            # Check if this line needs CTE bracket processing
            formatted_line = self._process_cte_brackets(logical_line.strip(), line_num)
            if formatted_line is None:
                # Check for CASE formatting
                if self._is_case_line(logical_line.strip()):
                    formatted_line = self._format_case_clause(logical_line.strip())
                else:
                    # Standard formatting - pass subquery context
                    formatted_line = self._format_line_preserving_tokens(logical_line.strip(), format_in_subquery)
                formatted_lines.append(formatted_line)
            else:
                # CTE bracket processing returned multiple lines
                bracket_lines = formatted_line.split('\n')
                formatted_lines.extend(bracket_lines)
            
            i += 1
        
        # Insert blank lines between CTEs and before main query
        formatted_lines = self._insert_cte_blank_lines(formatted_lines)
        
        return '\n'.join(formatted_lines)
    
    def _process_cte_brackets(self, line: str, line_num: int) -> Optional[str]:
        """Process CTE bracket formatting - opening bracket on same line as AS, closing bracket positioning"""
        # Check if this line contains AS ( or AS(
        if re.search(r'\bAS\s*\(', line, re.IGNORECASE):
            # Split at AS( or AS (
            parts = re.split(r'(\bAS)\s*\(', line, 1, re.IGNORECASE)
            if len(parts) >= 3:
                before_as = parts[0].strip()
                as_part = parts[1].strip()
                after_paren = parts[2].strip()
                
                # Format: "WITH cte_name AS (" on same line
                result_lines = []
                
                # First line: WITH cte_name AS (
                as_clause_with_paren = f"{before_as} {as_part} (".strip()
                formatted_as = self._format_line_preserving_tokens(as_clause_with_paren)
                result_lines.append(formatted_as)
                
                # Second line: content after opening parenthesis (if any)
                if after_paren:
                    formatted_content = self._format_line_preserving_tokens(after_paren)
                    result_lines.append(formatted_content)
                
                return '\n'.join(result_lines)
        
        # Check if this line is a closing bracket for CTE
        if line.strip() == ')':
            # Position closing bracket at river + 1
            close_paren_pos = self.primary_river_pos + 1
            return f"{' ' * close_paren_pos})"
        
        # Check if line ends with closing bracket
        if line.strip().endswith(')') and len(line.strip()) > 1:
            # Split content and closing bracket
            content = line.strip()[:-1].strip()
            if content:
                result_lines = []
                # Content line
                formatted_content = self._format_line_preserving_tokens(content)
                result_lines.append(formatted_content)
                # Closing bracket line
                close_paren_pos = self.primary_river_pos + 1
                result_lines.append(f"{' ' * close_paren_pos})")
                return '\n'.join(result_lines)
        
        return None  # No special bracket processing needed
    
    def _insert_cte_blank_lines(self, formatted_lines: List[str]) -> List[str]:
        """Insert blank lines between CTEs and before main query"""
        if not self.cte_structure or len(self.cte_structure) <= 1:
            return formatted_lines
        
        result_lines = []
        
        for i, line in enumerate(formatted_lines):
            # Add the current line
            result_lines.append(line)
            
            # Check if this line ends a CTE (closing bracket at river+1 position)
            if line.strip() == ')':
                expected_pos = self.primary_river_pos + 1
                actual_pos = len(line) - len(line.lstrip())
                
                if actual_pos == expected_pos:
                    # Look ahead to see what comes next (skip empty lines)
                    next_non_empty_line = None
                    for j in range(i + 1, len(formatted_lines)):
                        if formatted_lines[j].strip():
                            next_non_empty_line = formatted_lines[j]
                            break
                    
                    # If next line starts with comma (next CTE) or SELECT/other main clauses (main query)
                    if next_non_empty_line:
                        # Strip leading spaces to check if it starts with comma
                        stripped_next = next_non_empty_line.lstrip()
                        if (stripped_next.startswith(',') or 
                            any(stripped_next.upper().startswith(clause) 
                                for clause in ['SELECT', 'INSERT', 'UPDATE', 'DELETE'])):
                            result_lines.append('')  # Add blank line after CTE end
        
        return result_lines
    
    def _format_comment_line(self, line: str) -> str:
        """Format comment lines with proper indentation"""
        # Normalize multiple spaces after -- to single space
        comment_content = re.sub(r'^--\s*', '-- ', line)
        
        # Check for comment with SQL keywords (-- SELECT, -- JOIN, etc.)
        comment_clause_patterns = [
            (r'^--\s*,', '-- ,'),  # Comment comma
            (r'^--\s*(SELECT|FROM|WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+OUTER\s+JOIN|LEFT\s+OUTER\s+JOIN|RIGHT\s+OUTER\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN|UNION\s+ALL|UNION|WITH|AS|CREATE\s+TEMP\s+TABLE|CREATE\s+TABLE|INSERT\s+INTO|UPDATE|SET|DELETE|DECLARE|DO)\b', '-- {keyword}')
        ]
        
        for pattern, template in comment_clause_patterns:
            match = re.match(pattern, comment_content, re.IGNORECASE)
            if match:
                if '{keyword}' in template:
                    keyword = match.group(1).upper()
                    clause = f"-- {keyword}"
                else:
                    clause = template
                
                # Find remaining content after the keyword
                keyword_end = match.end()
                remaining = comment_content[keyword_end:].strip()
                
                clause_pos = self.primary_river_pos - len(clause)
                if remaining:
                    return f"{' ' * clause_pos}{clause} {remaining}"
                else:
                    return f"{' ' * clause_pos}{clause}"
        
        # Default comment (-- explanation text)
        clause = '--'
        remaining = comment_content[2:].strip()
        clause_pos = self.primary_river_pos - len(clause)
        if remaining:
            return f"{' ' * clause_pos}{clause} {remaining}"
        else:
            return f"{' ' * clause_pos}{clause}"
    
    def _is_case_clause(self, line: str) -> bool:
        """Check if line contains CASE statement clauses"""
        for pattern in self.secondary_clause_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def _format_case_clause(self, line: str) -> str:
        """Format CASE statement clauses using secondary river"""
        # Handle combined CASE WHEN THEN lines (comma-first)
        comma_case_match = re.match(r'(,\s*CASE\s+WHEN\s+.*?)\s+(THEN\s+.*)', line, re.IGNORECASE)
        if comma_case_match:
            comma_case_when_part = comma_case_match.group(1).strip()
            then_part = comma_case_match.group(2).strip()
            # Handle comma-first formatting
            comma_pos = self.primary_river_pos - 1  
            content_pos = self.primary_river_pos + 1
            # Extract just the CASE WHEN part without comma
            case_when_part = comma_case_when_part[1:].strip()  # Remove comma
            return f"{' ' * comma_pos},{' ' * (content_pos - comma_pos - 1)}{case_when_part} {then_part}"
        
        # Handle combined CASE WHEN THEN lines (non-comma)
        case_when_then_match = re.match(r'(CASE\s+WHEN\s+.*?)\s+(THEN\s+.*)', line, re.IGNORECASE)
        if case_when_then_match:
            case_when_part = case_when_then_match.group(1).strip()
            then_part = case_when_then_match.group(2).strip()
            # Position CASE at primary river, rest follows naturally
            case_pos = self.primary_river_pos - 4  # len('CASE')
            return f"{' ' * max(0, case_pos)}{case_when_part} {then_part}"
        
        # Handle combined WHEN THEN lines
        when_then_match = re.match(r'(WHEN\s+.*?)\s+(THEN\s+.*)', line, re.IGNORECASE)
        if when_then_match:
            when_part = when_then_match.group(1).strip()
            then_part = when_then_match.group(2).strip()
            # Position WHEN at secondary river, THEN follows naturally
            when_pos = self.secondary_river_pos - 4  # len('WHEN')
            return f"{' ' * max(0, when_pos)}{when_part} {then_part}"
        
        # Handle individual CASE clauses
        for pattern in self.secondary_clause_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                clause = match.group().strip().upper()
                remaining = line[len(match.group()):].strip()
                
                # Special handling for different CASE clauses
                if clause == 'CASE':
                    # CASE gets normal LEFT_CLAUSE positioning (primary river)
                    clause_pos = self.primary_river_pos - len(clause)
                elif clause in ['WHEN', 'THEN', 'ELSE']:
                    # WHEN/THEN/ELSE use secondary river positioning
                    # Secondary river = primary + 9 (fixed for CASE context)
                    clause_pos = self.secondary_river_pos - len(clause)
                elif clause == 'END':
                    # END positioned at secondary river (aligned with WHEN/THEN/ELSE)
                    clause_pos = self.secondary_river_pos - len(clause)
                else:
                    # Default secondary river position
                    clause_pos = self.secondary_river_pos - len(clause)
                
                if remaining:
                    return f"{' ' * max(0, clause_pos)}{clause} {remaining}"
                else:
                    return f"{' ' * max(0, clause_pos)}{clause}"
        
        # Fallback to standard formatting
        return self._format_line_preserving_tokens(line)
    
    def _is_subquery_line(self, line: str) -> bool:
        """Check if line contains subquery patterns"""
        # Look for (SELECT pattern - main indicator
        if re.search(r'\(\s*SELECT\b', line, re.IGNORECASE):
            return True
        
        # Don't treat other clauses as subquery unless they have clear subquery indicators
        return False
    
    def _is_case_line(self, line: str) -> bool:
        """Check if line is part of a CASE statement"""
        case_keywords = ['CASE', 'WHEN', 'THEN', 'ELSE', 'END']
        line_upper = line.strip().upper()
        
        for keyword in case_keywords:
            if line_upper.startswith(keyword + ' ') or line_upper == keyword:
                return True
        
        # Also check for CASE WHEN
        if re.match(r'\bCASE\s+WHEN\b', line, re.IGNORECASE):
            return True
            
        return False
    
    def _in_parentheses_context(self, line: str) -> bool:
        """Check if we're inside parentheses context (simplified check)"""
        # This is a simplified implementation - could be enhanced
        return False  # For now, rely on (SELECT pattern
    
    def _format_subquery_line(self, line: str) -> str:
        """Format subquery lines with nested indentation"""
        # Handle opening parenthesis with SELECT
        if re.search(r'\(\s*SELECT\b', line, re.IGNORECASE):
            # Split into parts: before (, SELECT, after SELECT
            match = re.search(r'(.*?)\(\s*(SELECT\b)(.*)', line, re.IGNORECASE)
            if match:
                before_paren = match.group(1).strip()
                select_keyword = match.group(2).upper()
                after_select = match.group(3).strip()
                
                result_lines = []
                
                # Format the part before ( if it exists
                if before_paren:
                    before_formatted = self._format_line_preserving_tokens(before_paren)
                    result_lines.append(before_formatted)
                
                # Add opening parenthesis at river + 1
                paren_pos = self.primary_river_pos + 1
                result_lines.append(f"{' ' * paren_pos}(")
                
                # Format SELECT with secondary river positioning
                if self.secondary_river_pos:
                    select_pos = self.secondary_river_pos - len(select_keyword)
                    if after_select:
                        select_line = f"{' ' * max(0, select_pos)}{select_keyword} {after_select}"
                    else:
                        select_line = f"{' ' * max(0, select_pos)}{select_keyword}"
                else:
                    # Fallback to standard formatting
                    if after_select:
                        select_line = self._format_line_preserving_tokens(f"{select_keyword} {after_select}")
                    else:
                        select_line = self._format_line_preserving_tokens(select_keyword)
                
                result_lines.append(select_line)
                return '\n'.join(result_lines)
        
        # Fallback to standard formatting
        return self._format_line_preserving_tokens(line)
    
    def _split_into_logical_lines(self, sql: str) -> List[str]:
        """Split SQL into logical lines for comma-first formatting"""
        sql = sql.strip()
        if not sql:
            return []
            
        lines = []
        current_tokens = []
        i = 0
        
        # Simple tokenization for splitting
        while i < len(sql):
            # Skip whitespace
            while i < len(sql) and sql[i].isspace():
                i += 1
            if i >= len(sql):
                break
                
            # Read next token
            token_start = i
            if sql[i] in ',;':
                # Single character tokens
                token = sql[i]
                i += 1
            else:
                # Multi-character tokens
                while i < len(sql) and not sql[i].isspace() and sql[i] not in ',;':
                    i += 1
                token = sql[token_start:i]
            
            if token == ',' and current_tokens:
                # End current line and start comma line
                if current_tokens:
                    lines.append(' '.join(current_tokens))
                    current_tokens = []
                # Start new line with comma
                current_tokens = [',']
                
            elif token == ';':
                # End current line and add semicolon line
                if current_tokens:
                    lines.append(' '.join(current_tokens))
                    current_tokens = []
                lines.append(';')
                
            elif token.upper() in ['SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'HAVING', 'UNION', 'AND', 'OR'] or token.startswith('--'):
                # Check for compound keywords
                if token.upper() in ['GROUP', 'ORDER', 'UNION'] and i < len(sql):
                    # Look ahead for BY/ALL
                    next_start = i
                    while next_start < len(sql) and sql[next_start].isspace():
                        next_start += 1
                    if next_start < len(sql):
                        if token.upper() == 'GROUP' and sql[next_start:next_start+2].upper() == 'BY':
                            # Skip whitespace and BY
                            while i < len(sql) and sql[i].isspace():
                                i += 1
                            i += 2  # Skip "BY"
                            token = 'GROUP BY'
                        elif token.upper() == 'ORDER' and sql[next_start:next_start+2].upper() == 'BY':
                            while i < len(sql) and sql[i].isspace():
                                i += 1
                            i += 2  # Skip "BY"
                            token = 'ORDER BY'
                        elif token.upper() == 'UNION' and sql[next_start:next_start+3].upper() == 'ALL':
                            while i < len(sql) and sql[i].isspace():
                                i += 1
                            i += 3  # Skip "ALL"
                            token = 'UNION ALL'
                
                # Start new line for major clauses (except AND/OR which continue)
                if token.upper() in ['AND', 'OR']:
                    # AND/OR start new lines
                    if current_tokens:
                        lines.append(' '.join(current_tokens))
                        current_tokens = []
                    current_tokens = [token]
                else:
                    # Other clauses start new lines
                    if current_tokens:
                        lines.append(' '.join(current_tokens))
                        current_tokens = []
                    current_tokens = [token]
            else:
                current_tokens.append(token)
        
        # Add final line
        if current_tokens:
            lines.append(' '.join(current_tokens))
            
        return lines
    
    def _format_line_preserving_tokens(self, line: str, in_subquery: bool = False) -> str:
        """Format a single line while preserving all original tokens"""
        if not line:
            return ''
        
        # For simple cases, handle SELECT + first item specially
        if line.strip().upper().startswith('SELECT '):
            # Extract SELECT and first item only
            content = line.strip()[7:]  # Remove "SELECT "
            
            # Choose river position based on context
            if (in_subquery and self.secondary_river_pos and 
                'SELECT' in self.secondary_clauses and 'CASE WHEN' in self.secondary_clauses):
                # Use secondary river positioning for subquery SELECT
                river_pos = self.secondary_river_pos
            else:
                # Use primary river positioning for main query SELECT
                river_pos = self.primary_river_pos
                
            select_pos = river_pos - len('SELECT')
            
            if ',' in content:
                # Has multiple items - take only first
                first_item = content.split(',')[0].strip()
                return f"{' ' * max(0, select_pos)}SELECT {first_item}"
            else:
                # Single item or no items
                return f"{' ' * max(0, select_pos)}SELECT {content}"
        
        # Handle comma-first lines
        if line.strip().startswith(','):
            content = line.strip()[1:].strip()  # Remove comma and whitespace
            comma_pos = self.primary_river_pos - 2  # Position 11 for river=13
            content_pos = self.primary_river_pos + 1  # Position 14 for river=13 (river+1)
            # User wants 1 space between comma and content, but content at river+1
            # This seems contradictory. Let me implement: comma at river-2, content at river+1, but only 1 space between
            # Solution: move comma to river-1 instead of river-2
            comma_pos = self.primary_river_pos - 1  # Position 12 for river=13
            spaces_after_comma = content_pos - comma_pos - 1  # 14 - 12 - 1 = 1 space
            return f"{' ' * comma_pos},{' ' * spaces_after_comma}{content}"
        
        # Handle comment lines
        if line.strip().startswith('--'):
            return self._format_comment_line(line.strip())
        
        # Handle CASE statement clauses
        if self._is_case_clause(line.strip()):
            return self._format_case_clause(line.strip())
        
        # Handle subquery patterns (SELECT within parentheses)
        if self._is_subquery_line(line.strip()):
            return self._format_subquery_line(line.strip())
        
        # Handle other LEFT_CLAUSE patterns with subquery context awareness
        for pattern in self.left_clause_patterns:
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                clause = match.group().strip()
                remaining = line.strip()[len(clause):].strip()
                
                # Use secondary river positioning if in subquery context and we have both contexts
                if (in_subquery and self.secondary_river_pos and 
                    'SELECT' in self.secondary_clauses and 'CASE WHEN' in self.secondary_clauses and
                    clause.upper() in ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING']):
                    # Use secondary river positioning for subquery clauses
                    clause_pos = self.secondary_river_pos - len(clause)
                else:
                    # Use primary river positioning for main query clauses
                    clause_pos = self.primary_river_pos - len(clause)
                
                if remaining:
                    return f"{' ' * max(0, clause_pos)}{clause} {remaining}"
                else:
                    return f"{' ' * max(0, clause_pos)}{clause}"
        
        # Handle AND/OR
        if line.strip().upper().startswith('AND ') or line.strip().upper().startswith('OR '):
            parts = line.strip().split(None, 1)
            operator = parts[0].upper()
            condition = parts[1] if len(parts) > 1 else ''
            operator_pos = self.primary_river_pos - len(operator)
            return f"{' ' * operator_pos}{operator} {condition}"
        
        # Handle semicolon
        if line.strip() == ';':
            semicolon_pos = self.primary_river_pos + 1
            return f"{' ' * semicolon_pos};"
        
        # Default - treat as RIGHT_SENTENCE continuation
        content = line.strip()
        content_pos = self.primary_river_pos + 1
        return f"{' ' * content_pos}{content}"
    
    def _format_tokens_on_line(self, tokens: List[Dict]) -> str:
        """Format all tokens that appear on a single line"""
        if not tokens:
            return ""
        
        # Analyze token structure
        left_clauses = [t for t in tokens if t['type'] == 'LEFT_CLAUSE']
        right_sentences = [t for t in tokens if t['type'] == 'RIGHT_SENTENCE']
        commas = [t for t in tokens if t['type'] == 'COMMA']
        semicolons = [t for t in tokens if t['type'] == 'SEMICOLON']
        
        if left_clauses and not commas:
            # LEFT_CLAUSE + content pattern
            left_clause = left_clauses[0]
            
            if left_clause.get('subtype') == 'LOGICAL_OP':
                # AND/OR positioning
                clause_pos = self.primary_river_pos - len(left_clause['content'])
            else:
                # Regular LEFT_CLAUSE positioning
                clause_pos = self.primary_river_pos - len(left_clause['content'])
            
            line = ' ' * max(0, clause_pos) + left_clause['content']
            
            # Add right sentences
            if right_sentences:
                content = ' '.join(t['content'] for t in right_sentences)
                line += ' ' + content
            
            # Add semicolon if present
            if semicolons:
                line += ';'
            
            return line
            
        elif commas and not left_clauses:
            # Comma-first pattern
            comma_pos = self.primary_river_pos - 2
            line = ' ' * max(0, comma_pos) + ','
            
            if right_sentences:
                # Position content at river + 1
                content = ' '.join(t['content'] for t in right_sentences)
                content_pos = self.primary_river_pos + 1
                current_pos = comma_pos + 1  # After comma
                spaces_needed = content_pos - current_pos
                line += ' ' * max(1, spaces_needed) + content
            
            return line
            
        elif right_sentences and not left_clauses and not commas:
            # Pure RIGHT_SENTENCE (continuation or standalone)
            content_pos = self.primary_river_pos + 1
            content = ' '.join(t['content'] for t in right_sentences)
            line = ' ' * max(0, content_pos) + content
            
            if semicolons:
                line += ';'
                
            return line
            
        elif semicolons and not left_clauses and not right_sentences and not commas:
            # Just semicolon
            semi_pos = self.primary_river_pos
            return ' ' * max(0, semi_pos) + ';'
            
        else:
            # Mixed or complex pattern - handle as best we can
            result = ""
            for token in tokens:
                if token['type'] == 'LEFT_CLAUSE':
                    if token.get('subtype') == 'LOGICAL_OP':
                        pos = self.primary_river_pos - len(token['content'])
                    else:
                        pos = self.primary_river_pos - len(token['content'])
                    result = ' ' * max(0, pos) + token['content'] + ' '
                elif token['type'] == 'COMMA':
                    pos = self.primary_river_pos - 2
                    result += ' ' * max(0, pos - len(result)) + ', '
                elif token['type'] == 'RIGHT_SENTENCE':
                    result += token['content'] + ' '
                elif token['type'] == 'SEMICOLON':
                    result += ';'
            
            return result.rstrip()
    
    def _tokenize_preserve_content(self, sql: str) -> List[Dict]:
        """Tokenize SQL preserving all original content"""
        tokens = []
        i = 0
        current_token = ""
        
        while i < len(sql):
            char = sql[i]
            
            if char == '\n':
                # Finish current token if exists
                if current_token.strip():
                    tokens.append(self._classify_token(current_token.strip()))
                    current_token = ""
                # Add newline token
                tokens.append({'type': 'NEWLINE', 'content': '\n'})
                
            elif char.isspace():
                # Finish current token if exists
                if current_token.strip():
                    tokens.append(self._classify_token(current_token.strip()))
                    current_token = ""
                # Collect whitespace
                whitespace = char
                j = i + 1
                while j < len(sql) and sql[j].isspace() and sql[j] != '\n':
                    whitespace += sql[j]
                    j += 1
                tokens.append({'type': 'WHITESPACE', 'content': whitespace})
                i = j - 1
                
            elif char == ',':
                # Finish current token if exists
                if current_token.strip():
                    tokens.append(self._classify_token(current_token.strip()))
                    current_token = ""
                # Add comma as separate token
                tokens.append({'type': 'COMMA', 'content': ','})
                
            elif char == ';':
                # Finish current token if exists  
                if current_token.strip():
                    tokens.append(self._classify_token(current_token.strip()))
                    current_token = ""
                # Add semicolon as separate token
                tokens.append({'type': 'SEMICOLON', 'content': ';'})
                
            else:
                current_token += char
            
            i += 1
        
        # Add final token if exists
        if current_token.strip():
            tokens.append(self._classify_token(current_token.strip()))
        
        return tokens
    
    def _classify_token(self, content: str) -> Dict:
        """Classify a token as LEFT_CLAUSE or RIGHT_SENTENCE"""
        # Special case for AND/OR - they are LEFT_CLAUSE but with special positioning
        if content.upper() in ['AND', 'OR']:
            return {'type': 'LEFT_CLAUSE', 'content': content, 'subtype': 'LOGICAL_OP'}
        
        # Check if it matches any LEFT CLAUSE pattern
        for pattern in self.left_clause_patterns:
            if re.match(pattern + r'$', content, re.IGNORECASE):
                return {'type': 'LEFT_CLAUSE', 'content': content}
        
        # Default to RIGHT_SENTENCE
        return {'type': 'RIGHT_SENTENCE', 'content': content}
    
    def _format_token(self, token: Dict) -> str:
        """Format a single token based on its type"""
        if token['type'] == 'LEFT_CLAUSE':
            # Position LEFT CLAUSE at river - clause_length
            clause_pos = self.primary_river_pos - len(token['content'])
            spaces = ' ' * max(0, clause_pos)
            return f"{spaces}{token['content']} "
            
        elif token['type'] == 'COMMA':
            # Position comma at river - 2, followed by space to reach river + 1
            comma_pos = self.primary_river_pos - 2
            spaces = ' ' * max(0, comma_pos)
            return f"{spaces}, "
            
        elif token['type'] == 'RIGHT_SENTENCE':
            # Position at river + 1
            content_pos = self.primary_river_pos + 1
            spaces = ' ' * max(0, content_pos)
            return f"{spaces}{token['content']}"
            
        elif token['type'] == 'SEMICOLON':
            # Position at river
            semi_pos = self.primary_river_pos
            spaces = ' ' * max(0, semi_pos)
            return f"{spaces};"
            
        else:
            return token['content']
    
    def _group_tokens_by_line_logic(self, tokens: List[Dict]) -> List[List[Dict]]:
        """Group tokens into logical lines based on SQL formatting rules"""
        groups = []
        current_group = []
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token['type'] == 'NEWLINE':
                # End current group if it has content
                if current_group:
                    groups.append(current_group)
                    current_group = []
                # Empty lines are preserved
                else:
                    groups.append([])
                    
            elif token['type'] == 'WHITESPACE':
                # Skip whitespace - we format our own
                pass
                
            elif token['type'] == 'LEFT_CLAUSE':
                # LEFT_CLAUSE starts a new logical line
                if current_group:
                    groups.append(current_group)
                    current_group = []
                current_group.append(token)
                
                # For SELECT, collect first item on same line, then start comma-first for rest
                if token['content'].upper() == 'SELECT':
                    # Collect first RIGHT_SENTENCE only
                    j = i + 1
                    found_first_sentence = False
                    while j < len(tokens):
                        next_token = tokens[j]
                        if next_token['type'] == 'LEFT_CLAUSE':
                            break
                        elif next_token['type'] == 'RIGHT_SENTENCE' and not found_first_sentence:
                            current_group.append(next_token)
                            found_first_sentence = True
                        elif next_token['type'] == 'COMMA' and found_first_sentence:
                            # Stop here - comma starts new line
                            break
                        elif next_token['type'] != 'WHITESPACE' and next_token['type'] != 'NEWLINE':
                            if found_first_sentence:
                                break
                        j += 1
                    i = j - 1
                else:
                    # Other LEFT_CLAUSES collect everything until next LEFT_CLAUSE
                    j = i + 1
                    while j < len(tokens):
                        next_token = tokens[j]
                        if next_token['type'] == 'LEFT_CLAUSE':
                            break
                        elif next_token['type'] != 'WHITESPACE' and next_token['type'] != 'NEWLINE':
                            current_group.append(next_token)
                        j += 1
                    i = j - 1
                
            elif token['type'] in ['COMMA', 'RIGHT_SENTENCE', 'SEMICOLON']:
                # These can start their own lines or continue existing ones
                if current_group:
                    # Check if this should be on the same line as previous
                    # For now, comma-first style means comma starts new line
                    if token['type'] == 'COMMA':
                        groups.append(current_group)
                        current_group = [token]
                        
                        # Look ahead for content after comma until newline or next clause
                        j = i + 1
                        while j < len(tokens):
                            next_token = tokens[j]
                            if next_token['type'] == 'LEFT_CLAUSE':
                                break
                            elif next_token['type'] == 'NEWLINE':
                                # Check if there's content after newline that belongs with this comma
                                k = j + 1
                                while k < len(tokens) and tokens[k]['type'] == 'WHITESPACE':
                                    k += 1
                                if k < len(tokens) and tokens[k]['type'] == 'RIGHT_SENTENCE':
                                    # Include the content after newline with this comma
                                    current_group.append(tokens[k])
                                    i = k
                                break
                            elif next_token['type'] == 'RIGHT_SENTENCE':
                                current_group.append(next_token)
                                break
                            j += 1
                        if j <= i:
                            i = j - 1
                    else:
                        current_group.append(token)
                else:
                    current_group.append(token)
            
            i += 1
        
        # Add final group if exists
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _format_token_group(self, token_group: List[Dict]) -> str:
        """Format a group of tokens that belong on the same line"""
        if not token_group:
            return ""
        
        # Analyze the group structure
        has_left_clause = any(t['type'] == 'LEFT_CLAUSE' for t in token_group)
        has_comma = any(t['type'] == 'COMMA' for t in token_group)
        
        if has_left_clause and not has_comma:
            # Standard LEFT_CLAUSE + RIGHT_SENTENCE pattern
            left_clause = next(t for t in token_group if t['type'] == 'LEFT_CLAUSE')
            right_sentences = [t for t in token_group if t['type'] == 'RIGHT_SENTENCE']
            
            # Check if this is a logical operator (AND/OR)
            if left_clause.get('subtype') == 'LOGICAL_OP':
                # Position AND/OR at river - len(operator)
                clause_pos = self.primary_river_pos - len(left_clause['content'])
                line = ' ' * max(0, clause_pos) + left_clause['content']
            else:
                # Position LEFT_CLAUSE normally
                clause_pos = self.primary_river_pos - len(left_clause['content'])
                line = ' ' * max(0, clause_pos) + left_clause['content']
            
            # Add RIGHT_SENTENCES
            if right_sentences:
                content = ' '.join(t['content'] for t in right_sentences)
                line += ' ' + content
                
            return line
            
        elif has_comma:
            # Comma-first pattern: , content
            right_sentences = [t for t in token_group if t['type'] == 'RIGHT_SENTENCE']
            
            # Position comma at river-2
            comma_pos = self.primary_river_pos - 2
            line = ' ' * max(0, comma_pos) + ','
            
            # Add content at river+1
            if right_sentences:
                content = ' '.join(t['content'] for t in right_sentences)
                content_pos = self.primary_river_pos + 1
                current_pos = comma_pos + 1  # After comma
                spaces_needed = content_pos - current_pos
                line += ' ' * max(1, spaces_needed) + content
                
            return line
            
        else:
            # Other patterns (semicolon, standalone RIGHT_SENTENCE)
            semicolons = [t for t in token_group if t['type'] == 'SEMICOLON']
            right_sentences = [t for t in token_group if t['type'] == 'RIGHT_SENTENCE']
            
            if semicolons and not right_sentences:
                # Just semicolon
                semi_pos = self.primary_river_pos
                return ' ' * max(0, semi_pos) + ';'
            elif right_sentences:
                # RIGHT_SENTENCE (potentially with semicolon)
                content = ' '.join(t['content'] for t in right_sentences)
                content_pos = self.primary_river_pos + 1
                line = ' ' * max(0, content_pos) + content
                
                if semicolons:
                    line += ';'
                    
                return line
            else:
                return ""
    
    
    
    def verify_river_lines(self, formatted_sql: str) -> bool:
        """Verify that river line positions contain only spaces"""
        lines = formatted_sql.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            if len(line) > self.primary_river_pos:
                char_at_river = line[self.primary_river_pos]
                # River position should always have space, except in CASE statement contexts
                is_case_context = any(clause_word in line.upper() for clause_word in ['WHEN ', 'THEN ', 'ELSE ', 'END '])
                if char_at_river != ' ' and not is_case_context:
                    print(f"River line verification failed at line {line_num}")
                    print(f"Expected space at position {self.primary_river_pos}, found: '{char_at_river}'")
                    print(f"Line: '{line}'")
                    return False
            elif line.strip():  # Non-empty line shorter than river position
                # This is OK for lines that end before the river
                pass
        
        return True

def main():
    try:
        sql = sys.stdin.read()
        
        if not sql.strip():
            print("-- No SQL input provided", file=sys.stderr)
            sys.exit(1)
        
        formatter = RiverFormatter()
        formatted = formatter.format_sql(sql)
        
        # Verify river lines
        if not formatter.verify_river_lines(formatted):
            print("Warning: River line verification failed", file=sys.stderr)
        
        print(formatted)
        
    except Exception as e:
        print(f"Format error: {str(e)}", file=sys.stderr)
        if 'sql' in locals() and sql.strip():
            print(sql)
        sys.exit(1)

if __name__ == '__main__':
    main()