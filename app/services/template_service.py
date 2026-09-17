from typing import Any, Dict, Optional, Tuple
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError
from app.core.exceptions import TemplateRenderError
from app.core.logging import logger


class TemplateService:
    """Dynamic message rendering engine using Jinja2."""

    def __init__(self):
        self.jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_content(
        self,
        body_template: str,
        subject_template: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], str]:
        """
        Renders subject and body with provided dictionary context.
        Returns: (rendered_subject, rendered_body)
        """
        context = data or {}
        rendered_subject = None

        try:
            if subject_template:
                subj_tmpl = self.jinja_env.from_string(subject_template)
                rendered_subject = subj_tmpl.render(**context)

            body_tmpl = self.jinja_env.from_string(body_template)
            rendered_body = body_tmpl.render(**context)

            return rendered_subject, rendered_body

        except (TemplateSyntaxError, UndefinedError) as e:
            logger.error(f"Template rendering failed: {e}")
            raise TemplateRenderError(f"Failed to render template variables: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected template rendering error: {e}")
            raise TemplateRenderError(f"Unexpected template render failure: {str(e)}")


template_service = TemplateService()
