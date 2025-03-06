from django.db import models

class AnswerWord(models.Model):
    answer_word = models.CharField(max_length=100, verbose_name="정답 단어")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록 날짜")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정 날짜")

    def __str__(self):
        return self.answer_word

class BaseWord(models.Model):
    base_word = models.CharField(max_length=100, verbose_name="비교 단어")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록 날짜")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정 날짜")

    def __str__(self):
        return self.base_word