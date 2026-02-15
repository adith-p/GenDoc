from .utils import Colors, MARKDOWN_AVAILABLE, WEASYPRINT_AVAILABLE


def convert_to_pdf(md_content, output_path):
    """Converts Markdown to PDF using WeasyPrint."""

    if not WEASYPRINT_AVAILABLE:
        print(f"{Colors.RED}Error: WeasyPrint not installed.{Colors.ENDC}")
        print(f"{Colors.YELLOW}Install: uv add weasyprint{Colors.ENDC}")
        return False

    if not MARKDOWN_AVAILABLE:
        print(f"{Colors.RED}Error: Markdown library not installed.{Colors.ENDC}")
        print(f"{Colors.YELLOW}Install: uv add markdown{Colors.ENDC}")
        return False

    print(f"  {Colors.BLUE}[*]{Colors.ENDC} Converting to PDF with WeasyPrint...")

    try:
        import markdown
        from weasyprint import HTML, CSS

        # Convert MD -> HTML
        html_content = markdown.markdown(
            md_content, extensions=["tables", "fenced_code", "attr_list"]
        )

        # Enhanced CSS for PDF
        css = """
            @page {
                size: A4;
                margin: 2.5cm;
                @bottom-center {
                    content: "Page " counter(page);
                    font-size: 9pt;
                    color: #777;
                }
            }
            body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 11pt; line-height: 1.6; color: #333; }
            h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; font-size: 24pt; page-break-after: avoid; }
            h2 { color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px; font-size: 18pt; page-break-after: avoid; }
            h3 { color: #34495e; margin-top: 25px; font-size: 15pt; font-weight: bold; page-break-after: avoid; }
            h4 { color: #34495e; font-size: 14pt; font-weight: bold; margin: 15px 0 10px 0; page-break-after: avoid; }
            
            /* Tables */
            table { border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 10pt; page-break-inside: auto; }
            tr { page-break-inside: avoid; page-break-after: auto; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; word-wrap: break-word; overflow-wrap: break-word; }
            th { background-color: #f8f9fa; font-weight: bold; color: #333; }
            
            /* Summary Table */
            .summary-table { table-layout: fixed; width: 100%; }
            .summary-table th:nth-child(1) { width: 30%; }
            .summary-table th:nth-child(2) { width: 12%; text-align: center; }
            .summary-table th:nth-child(3) { width: 28%; }
            .summary-table th:nth-child(4) { width: 30%; }
            .summary-table td { overflow: hidden; text-overflow: ellipsis; }
            .summary-table td:nth-child(2) { text-align: center; }
            
            .page-break-after { page-break-after: always; }
            
            code { background-color: #f4f4f4; font-family: 'Courier New', monospace; padding: 2px 4px; font-size: 10pt; border-radius: 3px; color: #e74c3c; word-break: break-all; }
            pre { background-color: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #eee; font-family: 'Courier New', monospace; font-size: 10pt; white-space: pre-wrap; margin: 15px 0; overflow-wrap: break-word; }
            pre code { background-color: transparent; padding: 0; color: #333; }
            blockquote { border-left: 4px solid #ddd; padding-left: 15px; margin: 15px 0; color: #666; font-style: italic; }
            
            /* Method badges */
            .method-get { background: #28a745; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-post { background: #007bff; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-put { background: #fd7e14; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-patch { background: #ffc107; color: #333; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-delete { background: #dc3545; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            
            /* Property badges */
            .prop-required { color: #d73a49; border: 1px solid #d73a49; padding: 1px 4px; border-radius: 3px; font-size: 8pt; font-weight: bold; }
            .prop-readonly { color: #0366d6; border: 1px solid #0366d6; padding: 1px 4px; border-radius: 3px; font-size: 8pt; font-weight: bold; }
            .prop-optional { color: #6a737d; border: 1px solid #6a737d; padding: 1px 4px; border-radius: 3px; font-size: 8pt; }
            
            details { margin: 10px 0; padding: 10px; background: #f9f9f9; border: 1px solid #eee; border-radius: 4px; }
            summary { font-weight: bold; cursor: pointer; color: #0366d6; }
        """

        html_doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>API Documentation</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        HTML(string=html_doc).write_pdf(output_path, stylesheets=[CSS(string=css)])
        return True

    except Exception as e:
        print(f"{Colors.RED}PDF generation failed: {e}{Colors.ENDC}")
        return False


def convert_to_html(md_content, output_path):
    """Converts Markdown content to a standalone, interactive HTML file."""

    if not MARKDOWN_AVAILABLE:
        print(f"{Colors.RED}Error: Markdown library not installed.{Colors.ENDC}")
        print(f"{Colors.YELLOW}Install: uv add markdown{Colors.ENDC}")
        return False

    try:
        import markdown

        # Convert MD -> HTML using extensions for tables and structure
        # Added md_in_html to support markdown syntax inside HTML block tags like <details>
        html_body_content = markdown.markdown(
            md_content,
            extensions=[
                "tables",
                "fenced_code",
                "toc",
                "sane_lists",
                "attr_list",
                "md_in_html",
            ],
        )

        # Enhanced HTML5 Template
        html_doc = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>API Documentation</title>
            <style>
                :root {{
                    --sidebar-width: 280px;
                    --header-height: 60px;
                    --primary-color: #0366d6;
                    --bg-color: #ffffff;
                    --text-color: #24292e;
                    --border-color: #e1e4e8;
                }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    color: var(--text-color);
                    background-color: var(--bg-color);
                    display: flex;
                    height: 100vh;
                    overflow: hidden;
                    font-size: 16px;
                }}

                /* Sidebar */
                #sidebar {{
                    width: var(--sidebar-width);
                    background-color: #f6f8fa;
                    border-right: 1px solid var(--border-color);
                    overflow-y: auto;
                    padding: 20px;
                    flex-shrink: 0;
                    display: flex;
                    flex-direction: column;
                }}
                
                #sidebar h2 {{
                    font-size: 1.2em;
                    margin-top: 0;
                    padding-bottom: 10px;
                    border-bottom: 1px solid var(--border-color);
                }}

                .nav-link {{
                    display: block;
                    padding: 8px 0;
                    color: var(--text-color);
                    text-decoration: none;
                    font-size: 0.9em;
                    border-bottom: 1px solid transparent;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}
                
                .nav-link:hover {{
                    color: var(--primary-color);
                    text-decoration: underline;
                }}

                /* Main Content */
                #main {{
                    flex-grow: 1;
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }}

                /* Header / Search Bar */
                #header {{
                    height: var(--header-height);
                    border-bottom: 1px solid var(--border-color);
                    padding: 0 30px;
                    display: flex;
                    align-items: center;
                    background-color: #fff;
                    flex-shrink: 0;
                    justify-content: space-between;
                }}

                #search-input {{
                    width: 300px;
                    padding: 8px 12px;
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    font-size: 14px;
                }}
                /* Current match highlight - different color */
                mark.highlight.current {{
                    background-color: #ff9632;
                    font-weight: bold;
                }}
                .controls button {{
                    padding: 6px 12px;
                    margin-left: 10px;
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    background: #f6f8fa;
                    cursor: pointer;
                    font-size: 13px;
                }}
                
                .controls button:hover {{
                    background-color: #e1e4e8;
                }}

                /* Content Area */
                #content {{
                    padding: 30px;
                    overflow-y: auto;
                    scroll-behavior: smooth;
                }}

                /* Endpoint Blocks (Created by JS) */
                .endpoint-block {{
                    margin-bottom: 30px;
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    padding: 20px;
                }}
                
                .endpoint-block h3 {{
                    margin-top: 0;
                    padding-bottom: 10px;
                    border-bottom: 1px solid var(--border-color);
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    font-size: 1.5em;
                }}
                
                .endpoint-block h3:hover {{
                    color: var(--primary-color);
                }}
                
                .endpoint-block h3::after {{
                    content: "▼";
                    font-size: 0.7em;
                    margin-left: auto;
                    color: #999;
                }}
                
                .endpoint-block.collapsed h3::after {{
                    content: "◀";
                }}
                
                .endpoint-block.collapsed > *:not(h3) {{
                    display: none;
                }}
                
                /* Increase size for Endpoint Path headers in HTML */
                h4 {{
                    font-size: 1.3em;
                    margin-top: 1.5em;
                }}

                /* Tables & Code */
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #dfe2e5; padding: 6px 13px; }}
                th {{ background-color: #f6f8fa; font-weight: 600; }}
                code {{ background-color: rgba(27,31,35,0.05); padding: 0.2em 0.4em; border-radius: 3px; font-family: monospace; font-size: 85%; }}
                pre {{ background-color: #f6f8fa; border-radius: 3px; font-size: 85%; padding: 16px; overflow: auto; }}
                details {{ border: 1px solid #e1e4e8; border-radius: 6px; padding: 0.5em; margin-bottom: 1em; }}
                summary {{ font-weight: bold; cursor: pointer; }}
                
                h2 {{ margin-top: 40px; }}

                /* Highlight style */
                mark.highlight {{
                    background-color: #ffe066;
                    color: black;
                    border-radius: 2px;
                    padding: 0 2px;
                }}
                
            </style>
        </head>
        <body>
            <div id="sidebar">
                <h2>Endpoints</h2>
                <div id="nav-links"></div>
            </div>
            
            <div id="main">
                <div id="header">
                    <div style="font-weight: bold; font-size: 1.2em;">API Docs</div>
                    <div class="controls">
                        <input type="text" id="search-input" placeholder="Search endpoints...">
                        <button onclick="previousMatch()" id="prev-btn" title="Previous match (Shift+Enter)">↑</button>
                        <button onclick="nextMatch()" id="next-btn" title="Next match (Enter)">↓</button>
                        <span id="match-counter" style="margin-left: 10px; font-size: 13px; color: #666;"></span>
                        <button onclick="expandAll()">Expand All</button>
                        <button onclick="collapseAll()">Collapse All</button>
                    </div>
                </div>
                
                <div id="content">
                    {html_body_content}
                </div>
            </div>
            <script>
                let currentMatchIndex = -1;
                let allMatches = [];

                document.addEventListener('DOMContentLoaded', () => {{
                    const content = document.getElementById('content');
                    const navLinksContainer = document.getElementById('nav-links');
                    
                    const headers = Array.from(content.querySelectorAll('h3'));
                    
                    headers.forEach(header => {{
                        const section = document.createElement('div');
                        section.className = 'endpoint-block';
                        
                        header.parentNode.insertBefore(section, header);
                        section.appendChild(header);
                        
                        let next = section.nextSibling;
                        while (next && next.tagName !== 'H3' && next.tagName !== 'H2' && next.tagName !== 'H1') {{
                            let sibling = next;
                            next = next.nextSibling;
                            section.appendChild(sibling);
                        }}
                        
                        header.addEventListener('click', () => {{
                            section.classList.toggle('collapsed');
                        }});
                        
                        const link = document.createElement('a');
                        link.className = 'nav-link';
                        link.textContent = header.textContent.replace(/`/g, '');
                        link.href = '#';
                        link.onclick = (e) => {{
                            e.preventDefault();
                            section.scrollIntoView({{ behavior: 'smooth' }});
                            section.style.borderColor = '#0366d6';
                            setTimeout(() => section.style.borderColor = '#e1e4e8', 2000);
                        }};
                        navLinksContainer.appendChild(link);
                    }});
                    
                    const searchInput = document.getElementById('search-input');
                    searchInput.addEventListener('keyup', (e) => {{
                        if (e.key === 'Enter') {{
                            if (e.shiftKey) {{
                                previousMatch();
                            }} else {{
                                nextMatch();
                            }}
                        }} else {{
                            performSearch();
                        }}
                    }});

                    updateNavigationButtons();
                }});
                
                function expandAll() {{
                    document.querySelectorAll('.endpoint-block').forEach(b => b.classList.remove('collapsed'));
                    document.querySelectorAll('details').forEach(d => d.open = true);
                }}
                
                function collapseAll() {{
                    document.querySelectorAll('.endpoint-block').forEach(b => b.classList.add('collapsed'));
                    document.querySelectorAll('details').forEach(d => d.open = false);
                }}

                function performSearch() {{
                    const term = document.getElementById('search-input').value.toLowerCase();
                    const blocks = document.querySelectorAll('.endpoint-block');
                    const navs = document.querySelectorAll('.nav-link');
                    
                    removeHighlights();
                    allMatches = [];
                    currentMatchIndex = -1;

                    blocks.forEach((block, index) => {{
                        const text = block.textContent.toLowerCase();
                        const isMatch = !term || text.includes(term);
                        
                        block.style.display = isMatch ? 'block' : 'none';
                        if (navs[index]) navs[index].style.display = isMatch ? 'block' : 'none';

                        if (term && isMatch) {{
                            highlightText(block, term);
                            block.classList.remove('collapsed');
                        }}
                    }});

                    allMatches = Array.from(document.querySelectorAll('mark.highlight'));
                    updateMatchCounter();
                    updateNavigationButtons();

                    if (allMatches.length > 0) {{
                        currentMatchIndex = 0;
                        scrollToMatch(0);
                    }}
                }}

                function highlightText(element, term) {{
                    if (!term) return;
                    const regex = new RegExp(`(${{term.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&')}})`, 'gi');
                    
                    function traverse(node) {{
                        if (node.nodeType === 3) {{
                            const match = node.data.match(regex);
                            if (match) {{
                                const fragment = document.createDocumentFragment();
                                let lastIdx = 0;
                                node.data.replace(regex, (match, p1, offset) => {{
                                    fragment.appendChild(document.createTextNode(node.data.slice(lastIdx, offset)));
                                    const mark = document.createElement('mark');
                                    mark.className = 'highlight';
                                    mark.textContent = match;
                                    fragment.appendChild(mark);
                                    lastIdx = offset + match.length;
                                    return match;
                                }});
                                fragment.appendChild(document.createTextNode(node.data.slice(lastIdx)));
                                node.parentNode.replaceChild(fragment, node);
                            }}
                            return;
                        }}
                        
                        if (node.nodeType === 1 && node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE' && node.tagName !== 'MARK') {{
                            Array.from(node.childNodes).forEach(traverse);
                        }}
                    }}
                    
                    traverse(element);
                }}

                function removeHighlights() {{
                    document.querySelectorAll('mark.highlight').forEach(mark => {{
                        const parent = mark.parentNode;
                        parent.replaceChild(document.createTextNode(mark.textContent), mark);
                        parent.normalize();
                    }});
                }}

                function nextMatch() {{
                    if (allMatches.length === 0) return;
                    
                    currentMatchIndex = (currentMatchIndex + 1) % allMatches.length;
                    scrollToMatch(currentMatchIndex);
                }}

                function previousMatch() {{
                    if (allMatches.length === 0) return;
                    
                    currentMatchIndex = currentMatchIndex <= 0 ? allMatches.length - 1 : currentMatchIndex - 1;
                    scrollToMatch(currentMatchIndex);
                }}

                function scrollToMatch(index) {{
                    if (index < 0 || index >= allMatches.length) return;

                    allMatches.forEach(mark => mark.classList.remove('current'));

                    const currentMark = allMatches[index];
                    currentMark.classList.add('current');
                    currentMark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});

                    updateMatchCounter();
                }}

                function updateMatchCounter() {{
                    const counter = document.getElementById('match-counter');
                    if (allMatches.length > 0) {{
                        counter.textContent = `${{currentMatchIndex + 1}} / ${{allMatches.length}}`;
                    }} else {{
                        counter.textContent = '';
                    }}
                }}

                function updateNavigationButtons() {{
                    const prevBtn = document.getElementById('prev-btn');
                    const nextBtn = document.getElementById('next-btn');
                    const hasMatches = allMatches.length > 0;

                    prevBtn.disabled = !hasMatches;
                    nextBtn.disabled = !hasMatches;

                    if (!hasMatches) {{
                        prevBtn.style.opacity = '0.5';
                        nextBtn.style.opacity = '0.5';
                        prevBtn.style.cursor = 'not-allowed';
                        nextBtn.style.cursor = 'not-allowed';
                    }} else {{
                        prevBtn.style.opacity = '1';
                        nextBtn.style.opacity = '1';
                        prevBtn.style.cursor = 'pointer';
                        nextBtn.style.cursor = 'pointer';
                    }}
                }}
            </script>
        </body>
        </html>
        """

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        return True
    except Exception as e:
        print(f"{Colors.RED}HTML generation failed: {e}{Colors.ENDC}")
        return False
