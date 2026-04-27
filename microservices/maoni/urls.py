from django.urls import path

from microservices.maoni.views import (
    MaoniCategoriesView,
    MaoniSuggestionDetailView,
    MaoniSuggestionPrintView,
    MaoniSuggestionReplyView,
    MaoniSuggestionsView,
)

urlpatterns = [
    path("maoni/suggestions/", MaoniSuggestionsView.as_view()),
    path("maoni/suggestions/<uuid:uid>/", MaoniSuggestionDetailView.as_view()),
    path("maoni/suggestions/<uuid:uid>/reply/", MaoniSuggestionReplyView.as_view()),
    path("maoni/suggestions/<uuid:uid>/print/", MaoniSuggestionPrintView.as_view()),
    path("maoni/categories/", MaoniCategoriesView.as_view()),
]
