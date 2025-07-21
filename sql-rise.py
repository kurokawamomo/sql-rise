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
        self.left_clauses = []
        
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
            
            # Other
            r'\bDECLARE\b', r'\bDO\b',
        ]
        
        # Continuation patterns (special LEFT CLAUSE)
        self.continuation_patterns = [
            r'^\s*,\s*',  # Comma continuation
            r'^\s*AND\b', r'^\s*OR\b',  # Logical operators
        ]
        
    def format_sql(self, sql: str) -> str:
        """Main entry point for SQL formatting"""
        if not sql.strip():
            return sql
            
        # Step 1: Global scan to find all LEFT CLAUSES
        self._extract_all_left_clauses(sql)
        
        # Step 2: Calculate primary river line position
        self._calculate_primary_river()
        
        # Step 3: Format the SQL
        formatted = self._format_with_river(sql)
        
        return formatted
    
    def _extract_all_left_clauses(self, sql: str):
        """Extract all LEFT CLAUSES from entire input to calculate global river"""
        self.left_clauses = []
        
        # Remove comments first for accurate pattern matching
        sql_clean = self._remove_comments(sql)
        
        # Find all LEFT CLAUSE patterns
        for pattern in self.left_clause_patterns:
            matches = re.finditer(pattern, sql_clean, re.IGNORECASE)
            for match in matches:
                clause = match.group().strip()
                # Normalize whitespace in multi-word clauses
                clause = ' '.join(clause.split())
                if clause not in self.left_clauses:
                    self.left_clauses.append(clause)
        
        # Also check for continuation commas and operators
        lines = sql_clean.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(','):
                self.left_clauses.append(',')
            elif line.startswith('AND ') or line.startswith('OR '):
                parts = line.split(None, 1)
                if parts:
                    self.left_clauses.append(parts[0])
    
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
    
    def _format_with_river(self, sql: str) -> str:
        """Format SQL using calculated river line - preserve all original tokens"""
        # First, split the SQL into logical formatting lines
        logical_lines = self._split_into_logical_lines(sql)
        
        formatted_lines = []
        for logical_line in logical_lines:
            if not logical_line.strip():
                formatted_lines.append('')
                continue
            
            formatted_line = self._format_line_preserving_tokens(logical_line.strip())
            formatted_lines.append(formatted_line)
        
        return '\n'.join(formatted_lines)
    
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
                
            elif token.upper() in ['SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'HAVING', 'UNION', 'AND', 'OR']:
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
    
    def _format_line_preserving_tokens(self, line: str) -> str:
        """Format a single line while preserving all original tokens"""
        if not line:
            return ''
        
        # For simple cases, handle SELECT + first item specially
        if line.strip().upper().startswith('SELECT '):
            # Extract SELECT and first item only
            content = line.strip()[7:]  # Remove "SELECT "
            if ',' in content:
                # Has multiple items - take only first
                first_item = content.split(',')[0].strip()
                river_pos = self.primary_river_pos
                select_pos = river_pos - len('SELECT')
                return f"{' ' * select_pos}SELECT {first_item}"
            else:
                # Single item or no items
                river_pos = self.primary_river_pos  
                select_pos = river_pos - len('SELECT')
                return f"{' ' * select_pos}SELECT {content}"
        
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
        
        # Handle other LEFT_CLAUSE patterns
        for pattern in self.left_clause_patterns:
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                clause = match.group().strip()
                remaining = line.strip()[len(clause):].strip()
                clause_pos = self.primary_river_pos - len(clause)
                if remaining:
                    return f"{' ' * clause_pos}{clause} {remaining}"
                else:
                    return f"{' ' * clause_pos}{clause}"
        
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
            comma = next(t for t in token_group if t['type'] == 'COMMA')
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
                if char_at_river != ' ':
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