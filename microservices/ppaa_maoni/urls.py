from django.urls import path
from .views import (
    SuggestionView,
    SuggestionDetailView,
    SuggestionReplyView,
    SuggestionPrintView,
    MaoniCategoryView,
)

app_name = 'ppaa_maoni'

urlpatterns = [
    path('suggestions/', SuggestionView.as_view(), name='suggestion-list'),
    path('suggestions/<str:uid>/', SuggestionDetailView.as_view(), name='suggestion-detail'),
    path('suggestions/<str:uid>/reply/', SuggestionReplyView.as_view(), name='suggestion-reply'),
    path('suggestions/<str:uid>/print/', SuggestionPrintView.as_view(), name='suggestion-print'),
    path('categories/', MaoniCategoryView.as_view(), name='category-list'),
]
