"""Who can see or edit an evaluation (§5.2, §6.4, §6.6). Never crosses organizations."""
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Evaluation


def visible_evaluations(user):
    """Finalized evaluations of the user's organization plus the user's own drafts."""
    return Evaluation.objects.filter(
        Q(organization_id=user.organization_id, status="finalizada")
        | Q(author_id=user.pk, organization_id=user.organization_id, status="borrador")
    ).select_related("software", "author", "catalog_version")


def get_visible_evaluation(user, pk):
    """404 for anything the user cannot see, including other organizations."""
    return get_object_or_404(visible_evaluations(user), pk=pk)


def get_editable_draft(user, pk):
    """404 outside the organization; 403 for someone else's draft or a finalized evaluation."""
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("software", "catalog_version"),
        pk=pk,
        organization_id=user.organization_id,
    )
    if evaluation.author_id != user.pk or evaluation.is_finalized:
        raise PermissionDenied("Solo puedes editar tus propios borradores.")
    return evaluation
