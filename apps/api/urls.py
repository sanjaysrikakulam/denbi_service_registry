"""API URL router."""

from rest_framework.routers import DefaultRouter
from .views import (
    BioToolsRecordViewSet,
    EdamTermViewSet,
    PrincipalInvestigatorViewSet,
    ServiceCategoryViewSet,
    ServiceCenterViewSet,
    SubmissionViewSet,
)

router = DefaultRouter()
router.register("submissions", SubmissionViewSet, basename="submission")
router.register("categories", ServiceCategoryViewSet, basename="category")
router.register("service-centers", ServiceCenterViewSet, basename="servicecenter")
router.register("pis", PrincipalInvestigatorViewSet, basename="pi")
router.register("edam", EdamTermViewSet, basename="edam")
router.register("biotools", BioToolsRecordViewSet, basename="biotools")

urlpatterns = router.urls
