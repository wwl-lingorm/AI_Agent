import os
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown2

class ReportGenerator:
    """
    统一的报告生成器，支持Markdown、HTML、PDF三种格式
    """
    def __init__(self, template_dir=None):
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def render_markdown(self, context: Dict[str, Any]) -> str:
        template = self.env.get_template('report.md.j2')
        return template.render(**context)

    def render_html(self, context: Dict[str, Any]) -> str:
        template = self.env.get_template('report.html.j2')
        return template.render(**context)

    def render_pdf(self, context: Dict[str, Any], output_path: str = None) -> bytes:
        html = self.render_html(context)
        try:
            from weasyprint import HTML
        except ImportError:
            raise RuntimeError('请先安装 weasyprint: pip install weasyprint')
        pdf_bytes = HTML(string=html).write_pdf()
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        return pdf_bytes
