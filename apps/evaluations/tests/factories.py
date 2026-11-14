"""Shared test builders for evaluations (used by evaluations and exports tests)."""
from apps.evaluations import workflow
from apps.evaluations.models import EvaluationSubfactor


def finished_evaluation(user, software, importance=3, answer=4):
    """A finalized evaluation where every factor gets `importance` and every subfactor `answer`."""
    evaluation = workflow.create_evaluation(user, software)
    for ev_factor in evaluation.factors.all():
        workflow.set_decision_importance(ev_factor, importance)
    workflow.start_stage_two(evaluation)
    for row in EvaluationSubfactor.objects.filter(evaluation_factor__evaluation=evaluation):
        workflow.answer_subfactor(evaluation, row.pk, answer)
    return workflow.finalize(evaluation)
