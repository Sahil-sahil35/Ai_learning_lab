"""
Comprehensive report generator for ML training results.
Supports PDF, HTML, and JSON formats with customizable templates.
"""

import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, blue
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import base64
import io

class ReportGenerator:
    """Generate professional ML training reports."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.custom_styles = self._create_custom_styles()
        plt.style.use('seaborn-v0_8')

    def _create_custom_styles(self) -> Dict[str, ParagraphStyle]:
        """Create custom paragraph styles."""
        styles = {}

        styles['title'] = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#2c3e50')
        )

        styles['subtitle'] = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            spaceAfter=20,
            spaceBefore=20,
            textColor=HexColor('#34495e')
        )

        styles['section'] = ParagraphStyle(
            'CustomSection',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=15,
            textColor=HexColor('#2980b9')
        )

        styles['body'] = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            leading=14,
            textColor=black
        )

        styles['metric'] = ParagraphStyle(
            'CustomMetric',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=HexColor('#27ae60')
        )

        return styles

    def generate_pdf_report(self, model_run: Any, config: Dict[str, Any],
                          output_path: str) -> str:
        """Generate comprehensive PDF report."""
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )

            story = []

            # Title page
            story.extend(self._create_title_page(model_run, config))

            # Executive Summary
            story.extend(self._create_executive_summary(model_run))

            # Data Analysis Section
            if model_run.analysis_results:
                story.extend(self._create_data_analysis_section(model_run))

            # Methodology Section
            story.extend(self._create_methodology_section(model_run))

            # Results Section
            if model_run.final_metrics:
                story.extend(self._create_results_section(model_run))

            # Visualizations
            if config.get('include_charts', True):
                story.extend(self._create_visualizations_section(model_run, output_path))

            # Conclusions
            story.extend(self._create_conclusions_section(model_run))

            # Appendices
            if config.get('include_appendices', False):
                story.extend(self._create_appendices_section(model_run))

            # Build PDF
            doc.build(story)

            return output_path

        except Exception as e:
            raise Exception(f"Error generating PDF report: {e}")

    def generate_html_report(self, model_run: Any, config: Dict[str, Any],
                           output_path: str) -> str:
        """Generate interactive HTML report."""
        try:
            html_content = self._create_html_template()

            # Replace placeholders with actual content
            html_content = html_content.replace('{{TITLE}}', f'ML Training Report - {model_run.id}')
            html_content = html_content.replace('{{MODEL_NAME}}', model_run.model_id_str)
            html_content = html_content.replace('{{GENERATED_DATE}}', datetime.datetime.now().strftime('%B %d, %Y'))

            # Add content sections
            sections = []

            # Executive Summary
            sections.append(self._create_html_executive_summary(model_run))

            # Metrics
            if model_run.final_metrics:
                sections.append(self._create_html_metrics_section(model_run))

            # Charts
            if config.get('include_charts', True):
                sections.append(self._create_html_charts_section(model_run, output_path))

            # Combine sections
            content_html = '\n'.join(sections)
            html_content = html_content.replace('{{CONTENT}}', content_html)

            # Write HTML file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            return output_path

        except Exception as e:
            raise Exception(f"Error generating HTML report: {e}")

    def generate_json_report(self, model_run: Any, config: Dict[str, Any],
                           output_path: str) -> str:
        """Generate structured JSON report."""
        try:
            report_data = {
                'metadata': {
                    'report_id': str(model_run.id),
                    'model_name': model_run.model_id_str,
                    'generated_at': datetime.datetime.utcnow().isoformat(),
                    'generated_by': 'ML LearnLab Platform',
                    'format_version': '1.0'
                },
                'training_info': {
                    'status': model_run.status,
                    'created_at': model_run.created_at.isoformat(),
                    'started_at': model_run.started_at.isoformat() if model_run.started_at else None,
                    'completed_at': model_run.completed_at.isoformat() if model_run.completed_at else None,
                    'duration_seconds': None
                },
                'configuration': config,
                'analysis_results': model_run.analysis_results,
                'final_metrics': model_run.final_metrics,
                'educational_summary': model_run.educational_summary,
                'data_quality': self._assess_data_quality(model_run),
                'model_performance': self._extract_performance_metrics(model_run),
                'recommendations': self._generate_recommendations(model_run)
            }

            # Calculate duration if available
            if model_run.started_at and model_run.completed_at:
                duration = model_run.completed_at - model_run.started_at
                report_data['training_info']['duration_seconds'] = duration.total_seconds()

            # Write JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, default=str)

            return output_path

        except Exception as e:
            raise Exception(f"Error generating JSON report: {e}")

    def _create_title_page(self, model_run: Any, config: Dict[str, Any]) -> List:
        """Create title page content."""
        content = []

        # Title
        content.append(Paragraph("Machine Learning Training Report", self.custom_styles['title']))
        content.append(Spacer(1, 30))

        # Subtitle
        content.append(Paragraph(f"Model: {model_run.model_id_str}", self.custom_styles['subtitle']))
        content.append(Paragraph(f"Run ID: {model_run.id}", self.custom_styles['subtitle']))
        content.append(Spacer(1, 40))

        # Report info
        info_data = [
            ['Generated Date:', datetime.datetime.now().strftime('%B %d, %Y')],
            ['Training Status:', model_run.status],
            ['Model Type:', model_run.model_id_str],
            ['User:', model_run.user.username if model_run.user else 'Unknown']
        ]

        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7'))
        ]))

        content.append(info_table)
        content.append(PageBreak())

        return content

    def _create_executive_summary(self, model_run: Any) -> List:
        """Create executive summary section."""
        content = []

        content.append(Paragraph("Executive Summary", self.custom_styles['subtitle']))
        content.append(Spacer(1, 12))

        summary_text = self._generate_executive_summary_text(model_run)
        content.append(Paragraph(summary_text, self.custom_styles['body']))
        content.append(Spacer(1, 20))

        # Key metrics table
        if model_run.final_metrics:
            metrics_data = [['Metric', 'Value']]
            for key, value in model_run.final_metrics.items():
                if isinstance(value, (int, float)):
                    metrics_data.append([key.replace('_', ' ').title(), f"{value:.4f}"])
                else:
                    metrics_data.append([key.replace('_', ' ').title(), str(value)])

            metrics_table = Table(metrics_data, colWidths=[2*inch, 2*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7'))
            ]))

            content.append(metrics_table)

        return content

    def _create_data_analysis_section(self, model_run: Any) -> List:
        """Create data analysis section."""
        content = []

        content.append(Paragraph("Data Analysis", self.custom_styles['subtitle']))
        content.append(Spacer(1, 12))

        if model_run.analysis_results:
            # Dataset overview
            analysis_text = "The dataset was analyzed to understand its characteristics and quality."
            content.append(Paragraph(analysis_text, self.custom_styles['body']))

            # Data statistics table
            if 'statistics' in model_run.analysis_results:
                stats_data = [['Statistic', 'Value']]
                for key, value in model_run.analysis_results['statistics'].items():
                    stats_data.append([key.replace('_', ' ').title(), str(value)])

                stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch])
                stats_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#e74c3c')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ecf0f1')),
                    ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7'))
                ]))

                content.append(Spacer(1, 12))
                content.append(stats_table)

        return content

    def _create_results_section(self, model_run: Any) -> List:
        """Create results section."""
        content = []

        content.append(Paragraph("Results & Performance", self.custom_styles['subtitle']))
        content.append(Spacer(1, 12))

        if model_run.final_metrics:
            # Performance analysis
            performance_text = "The model was evaluated using various metrics to assess its performance."
            content.append(Paragraph(performance_text, self.custom_styles['body']))
            content.append(Spacer(1, 12))

            # Performance highlights
            highlights = self._extract_performance_highlights(model_run.final_metrics)
            for highlight in highlights:
                content.append(Paragraph(f"• {highlight}", self.custom_styles['body']))

        return content

    def _create_visualizations_section(self, model_run: Any, output_path: str) -> List:
        """Create visualizations section with charts."""
        content = []

        content.append(Paragraph("Visualizations", self.custom_styles['subtitle']))
        content.append(Spacer(1, 12))

        try:
            # Generate charts directory
            charts_dir = Path(output_path).parent / 'charts'
            charts_dir.mkdir(exist_ok=True)

            # Create performance chart
            chart_path = self._create_performance_chart(model_run, charts_dir)
            if chart_path and os.path.exists(chart_path):
                content.append(Paragraph("Model Performance Metrics", self.custom_styles['section']))
                img = Image(chart_path, width=5*inch, height=3*inch)
                content.append(img)
                content.append(Spacer(1, 12))

        except Exception as e:
            # Add text placeholder if chart creation fails
            content.append(Paragraph(f"Visualizations could not be generated: {e}", self.custom_styles['body']))

        return content

    def _create_conclusions_section(self, model_run: Any) -> List:
        """Create conclusions section."""
        content = []

        content.append(Paragraph("Conclusions & Insights", self.custom_styles['subtitle']))
        content.append(Spacer(1, 12))

        # Educational insights
        if model_run.educational_summary:
            insights = model_run.educational_summary.get('insights', [])
            for insight in insights:
                content.append(Paragraph(f"• {insight}", self.custom_styles['body']))

        # Recommendations
        recommendations = self._generate_recommendations(model_run)
        if recommendations:
            content.append(Spacer(1, 12))
            content.append(Paragraph("Recommendations:", self.custom_styles['section']))
            for rec in recommendations:
                content.append(Paragraph(f"• {rec}", self.custom_styles['body']))

        return content

    def _create_html_template(self) -> str:
        """Create HTML template for reports."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        .header { text-align: center; border-bottom: 2px solid #3498db; padding-bottom: 20px; margin-bottom: 30px; }
        .section { margin: 30px 0; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #2ecc71; }
        .metric-label { font-size: 14px; color: #7f8c8d; margin-top: 5px; }
        .chart-container { margin: 20px 0; text-align: center; }
        .recommendation { background: #e8f5e8; padding: 15px; border-left: 4px solid #27ae60; margin: 10px 0; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>Machine Learning Training Report</h1>
        <p><strong>Model:</strong> {{MODEL_NAME}} | <strong>Generated:</strong> {{GENERATED_DATE}}</p>
    </div>

    <div class="content">
        {{CONTENT}}
    </div>
</body>
</html>
        '''

    def _create_performance_chart(self, model_run: Any, charts_dir: Path) -> str:
        """Create performance visualization chart."""
        try:
            if not model_run.final_metrics:
                return None

            # Extract numeric metrics
            numeric_metrics = {}
            for key, value in model_run.final_metrics.items():
                if isinstance(value, (int, float)):
                    numeric_metrics[key] = value

            if not numeric_metrics:
                return None

            # Create chart
            plt.figure(figsize=(10, 6))
            metrics_names = list(numeric_metrics.keys())
            metrics_values = list(numeric_metrics.values())

            bars = plt.bar(metrics_names, metrics_values, color='skyblue', alpha=0.7)
            plt.title('Model Performance Metrics', fontsize=16, fontweight='bold')
            plt.xlabel('Metrics', fontsize=12)
            plt.ylabel('Values', fontsize=12)
            plt.xticks(rotation=45, ha='right')

            # Add value labels on bars
            for bar, value in zip(bars, metrics_values):
                plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                        f'{value:.3f}', ha='center', va='bottom')

            plt.tight_layout()

            # Save chart
            chart_path = charts_dir / 'performance_metrics.png'
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()

            return str(chart_path)

        except Exception as e:
            print(f"Error creating performance chart: {e}")
            return None

    def _generate_executive_summary_text(self, model_run: Any) -> str:
        """Generate executive summary text."""
        summary = f"This report presents the results of training a {model_run.model_id_str} machine learning model. "

        if model_run.status == 'SUCCESS':
            summary += "The training was completed successfully. "
            if model_run.final_metrics:
                summary += "Key performance metrics indicate "
                # Add specific metric insights
                if 'accuracy' in model_run.final_metrics:
                    acc = model_run.final_metrics['accuracy']
                    summary += f"an accuracy of {acc:.2%}. "
        else:
            summary += f"The training process encountered issues and resulted in a {model_run.status} status. "

        return summary

    def _extract_performance_highlights(self, metrics: Dict[str, Any]) -> List[str]:
        """Extract key performance highlights from metrics."""
        highlights = []

        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if 'accuracy' in key.lower():
                    highlights.append(f"Model achieved {value:.2%} accuracy")
                elif 'loss' in key.lower():
                    highlights.append(f"Final loss: {value:.4f}")
                elif 'f1' in key.lower():
                    highlights.append(f"F1-Score: {value:.4f}")
                elif 'precision' in key.lower():
                    highlights.append(f"Precision: {value:.4f}")
                elif 'recall' in key.lower():
                    highlights.append(f"Recall: {value:.4f}")

        return highlights

    def _generate_recommendations(self, model_run: Any) -> List[str]:
        """Generate recommendations based on model performance."""
        recommendations = []

        if not model_run.final_metrics:
            return ["Train the model to generate performance-based recommendations"]

        metrics = model_run.final_metrics

        # Accuracy-based recommendations
        if 'accuracy' in metrics:
            acc = metrics['accuracy']
            if acc < 0.7:
                recommendations.append("Consider feature engineering to improve model performance")
            elif acc > 0.95:
                recommendations.append("Check for potential overfitting - consider regularization")
            else:
                recommendations.append("Model performance is acceptable - consider hyperparameter tuning for further improvement")

        # General recommendations
        recommendations.extend([
            "Validate the model on a separate test dataset",
            "Consider cross-validation for more robust performance estimation",
            "Monitor model performance in production for potential drift"
        ])

        return recommendations

    def _assess_data_quality(self, model_run: Any) -> Dict[str, Any]:
        """Assess data quality based on analysis results."""
        quality_assessment = {
            'overall_score': 0.8,  # Default score
            'issues': [],
            'strengths': []
        }

        if model_run.analysis_results:
            # Analyze based on available analysis results
            if 'missing_values' in model_run.analysis_results:
                missing_pct = model_run.analysis_results['missing_values'].get('percentage', 0)
                if missing_pct > 10:
                    quality_assessment['issues'].append(f"High missing value rate: {missing_pct}%")
                else:
                    quality_assessment['strengths'].append("Low missing value rate")

        return quality_assessment

    def _extract_performance_metrics(self, model_run: Any) -> Dict[str, Any]:
        """Extract and format performance metrics."""
        if not model_run.final_metrics:
            return {}

        formatted_metrics = {}
        for key, value in model_run.final_metrics.items():
            if isinstance(value, (int, float)):
                formatted_metrics[key] = {
                    'value': value,
                    'formatted': f"{value:.4f}",
                    'type': 'numeric'
                }
            else:
                formatted_metrics[key] = {
                    'value': value,
                    'formatted': str(value),
                    'type': 'categorical'
                }

        return formatted_metrics