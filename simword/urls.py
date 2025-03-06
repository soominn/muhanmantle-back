# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('total/', views.answer_word_count, name='answer_word_count'),
    path('<int:id>/<str:input_word>/', views.calculate_similarity, name='calculate_similarity'),
    path('<int:id>/', views.get_similarity_rank_list, name='get_similarity_rank_list'),
]
