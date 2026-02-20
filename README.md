# 🍃 DRF DocMint

<p align="center">
  <em>A zero-runtime CLI tool for generating beautiful, static API documentation for Django REST Framework projects.</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#output-formats">Output Formats</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#contributing">Contributing</a>
</p>

---

## ✨ Features

- **🔍 Zero Configuration**: Automatically detects DRF serializers, viewsets, APIViews, and query parameters using AST-based static analysis
- **📝 Multiple Output Formats**: 
  - Markdown
  - HTML (standalone, styled)
  - PDF (via WeasyPrint)
  - OpenAPI 3.0 (JSON/YAML)
  - Postman Collection v2.1
- **🚀 No Runtime Required**: Pure static analysis—no Django server needed
- **🎨 Beautiful Output**: Clean, modern documentation with syntax highlighting and responsive design
- **🔧 Smart Detection**: 
  - Auto-detects serializer classes
  - Identifies request/response serializers per HTTP method
  - Extracts query parameters from code
  - Handles nested serializers and relationships
  - Detects raw request body usage

## 📦 Installation

### Using pip

```bash
pip install drf-docmint
```

### Using uv (recommended)

```bash
uv add drf-docmint
```

### With PDF Support

```bash
# Using pip
pip install drf-docmint[pdf]

# Using uv
uv add drf-docmint --extra pdf
```

## 🚀 Usage

### Basic Command

Navigate to your Django project root and run:

```bash
doc-mint
```

This will scan your project and generate documentation in all available formats.

### Command Options

```bash
doc-mint [OPTIONS]
```

**Options:**
- `--format`, `-f`: Output format (choices: `markdown`, `html`, `pdf`, `openapi`, `postman`, `all`)
- `--output`, `-o`: Output directory (default: `./docs`)
- `--project-name`, `-n`: Project name for documentation
- `--verbose`, `-v`: Enable verbose output
- `--help`: Show help message

### Examples

```bash
# Generate only HTML documentation
doc-mint --format html

# Generate OpenAPI spec in custom directory
doc-mint --format json --output -d ./api-docs
doc-mint --format yaml --output -d ./api-docs

# Generate Postman collection v2.1
doc-mint --format postman --output ./api-docs

postman
# Verbose output
doc-mint -vb
```

## 📄 Output Formats

### Markdown
Clean, readable documentation perfect for GitHub wikis or static site generators.

### HTML
Standalone HTML file with embedded CSS—no external dependencies. Features:
- Responsive design
- Syntax-highlighted code examples
- Collapsible sections
- Search-friendly structure

### PDF
Professional PDF documentation generated from HTML using WeasyPrint.

### OpenAPI 3.0
Standard OpenAPI specification in JSON or YAML format. Compatible with:
- Swagger UI
- Redoc
- Postman (import)
- API testing tools

### Postman Collection
Ready-to-import Postman collection v2.1 with all detected endpoints.

## 🔧 How It Works

DRF DocMint uses **Abstract Syntax Tree (AST) parsing** to analyze your Python code without executing it:

1. **Discovery**: Scans your project for DRF views and serializers
2. **Analysis**: Parses ViewSets, APIViews, and Serializer classes
3. **Extraction**: Identifies:
   - HTTP methods (GET, POST, PUT, PATCH, DELETE)
   - Request/response serializers
   - Query parameters
   - Field types and validators
   - Nested relationships
4. **Generation**: Renders documentation in your chosen format(s)

**No Django server required!** Perfect for CI/CD pipelines and documentation automation.

## 📋 Requirements

- Python >= 3.10
- Django REST Framework project structure

### Dependencies

- `markdown` >= 3.10.2
- `pyyaml` >= 6.0.3
- `rich` >= 14.3.2
- `textual` >= 7.5.0
- `typer` >= 0.23.1

### Optional (for PDF generation)

- `weasyprint` >= 68.1

## 🏗️ Project Structure

```
your-django-project/
├── myapp/
│   ├── views.py      # DRF ViewSets and APIViews
│   ├── serializers.py
│   └── urls.py
└── docs/              # Generated documentation (default output)
    ├── api-docs.md
    ├── api-docs.html
    ├── api-docs.pdf
    ├── openapi.json
    └── postman-collection.json
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/adith-p/drf-docmint.git
cd drf-docmint

# Install dependencies with uv
uv sync

# Run the tool locally
uv run doc-mint
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🐛 Issues & Support

Found a bug or have a feature request? Please open an issue on [GitHub Issues](https://github.com/adith-p/drf-docmint/issues).

## 👨‍💻 Author

**Adith P**
- Email: adithprakash008@gmail.com
- GitHub: [@adith-p](https://github.com/adith-p)

---

<p align="center">
  Made with ❤️ for the Django REST Framework community
</p>
