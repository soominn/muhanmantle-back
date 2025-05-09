from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .models import AnswerWord, BaseWord

class SimilarityViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # 정답 단어와 후보 단어 설정
        self.answer_word = AnswerWord.objects.create(answer_word="신문")

        self.base_words = ["기사", "잡지", "종이", "세탁", "무료", "뉴스"]
        for word in self.base_words:
            BaseWord.objects.create(base_word=word)

    def test_similarity_rank_list(self):
        url = reverse("get_similarity_rank_list", kwargs={"id": self.answer_word.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["answer_word"], "신문")
        self.assertTrue("top_100_similarities" in data)
        self.assertGreater(len(data["top_100_similarities"]), 0)

    def test_calculate_similarity(self):
        input_word = "기사"
        url = reverse("calculate_similarity", kwargs={"id": self.answer_word.id, "input_word": input_word})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["input_word"], input_word)
        self.assertTrue("similarity_percentage" in data)
        self.assertTrue(isinstance(data["similarity_percentage"], float))
        self.assertIn("rank", data)
