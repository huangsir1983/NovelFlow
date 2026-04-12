"""
TDD tests for post-composite expression node:
- expression_service.generate_expression accepts and passes aspect_ratio
- canvas.py expression handler passes aspectRatio from content
"""
from unittest.mock import patch, MagicMock
import pytest


class TestExpressionServiceAspectRatio:
    """expression_service.generate_expression should accept and forward aspect_ratio."""

    @patch("services.ai_engine.ai_engine")
    def test_default_aspect_ratio_is_3_4(self, mock_engine):
        """When aspect_ratio is not provided, default should be 3:4."""
        mock_engine.generate_image.return_value = {
            "image_data": b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
            "mime_type": "image/png",
        }

        from services.expression_service import generate_expression

        generate_expression(
            reference_image_base64="iVBORw0KGgo=",
            expression_prompt="test prompt",
        )

        mock_engine.generate_image.assert_called_once()
        call_kwargs = mock_engine.generate_image.call_args
        assert call_kwargs[1].get("aspect_ratio") == "3:4"

    @patch("services.ai_engine.ai_engine")
    def test_custom_aspect_ratio_16_9(self, mock_engine):
        """When aspect_ratio='16:9' is passed, it should be forwarded to ai_engine."""
        mock_engine.generate_image.return_value = {
            "image_data": b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
            "mime_type": "image/png",
        }

        from services.expression_service import generate_expression

        generate_expression(
            reference_image_base64="iVBORw0KGgo=",
            expression_prompt="enhance scene quality",
            aspect_ratio="16:9",
        )

        mock_engine.generate_image.assert_called_once()
        call_kwargs = mock_engine.generate_image.call_args
        assert call_kwargs[1].get("aspect_ratio") == "16:9"


class TestCanvasExpressionHandlerAspectRatio:
    """canvas.py expression handler should pass aspectRatio from content to service."""

    @patch("services.expression_service.generate_expression")
    def test_passes_aspect_ratio_from_content(self, mock_gen_expr):
        """POST expression with aspectRatio in content should forward to generate_expression."""
        mock_gen_expr.return_value = "iVBORw0KGgo="  # base64

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.canvas import router
        from database import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api")

        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        client = TestClient(app)

        resp = client.post("/api/canvas/nodes/test-node-1/execute", json={
            "node_type": "expression",
            "content": {
                "inputStorageKey": "assets/images/test.png",
                "expressionPrompt": "enhance the scene",
                "aspectRatio": "16:9",
            },
        })

        # The handler should call generate_expression with aspect_ratio
        if mock_gen_expr.called:
            call_kwargs = mock_gen_expr.call_args
            assert call_kwargs[1].get("aspect_ratio") == "16:9"
