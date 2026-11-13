"""Decisor history screens H01-H03."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.core.decorators import decisor_required

from . import workflow
from .models import Evaluation


@decisor_required
@require_POST
def delete_draft(request, pk):
    """H03 / E4 'Descartar evaluación': only the author's own drafts (§3, §6.6)."""
    evaluation = get_object_or_404(Evaluation, pk=pk, organization_id=request.user.organization_id)
    workflow.delete_draft(evaluation, request.user)
    messages.success(request, f"Se eliminó el borrador de {evaluation.software}.")
    return redirect("/historial/")
