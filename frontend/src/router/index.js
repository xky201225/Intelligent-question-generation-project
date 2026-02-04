import { createRouter, createWebHistory } from 'vue-router'

import DictsPage from '../views/DictsPage.vue'
import AiReviewPage from '../views/AiReviewPage.vue'
import QuestionsPage from '../views/QuestionsPage.vue'
import PaperGeneratePage from '../views/PaperGeneratePage.vue'
import PapersManagePage from '../views/PapersManagePage.vue'
import AnswerSheetsPage from '../views/AnswerSheetsPage.vue'
import TextbooksPage from '../views/TextbooksPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dicts' },
    { path: '/dicts', component: DictsPage },
    { path: '/ai-review', component: AiReviewPage },
    { path: '/textbooks', component: TextbooksPage },
    { path: '/questions', component: QuestionsPage },
    { path: '/paper-generate', component: PaperGeneratePage },
    { path: '/papers', component: PapersManagePage },
    { path: '/answer-sheets', component: AnswerSheetsPage },
  ],
})
