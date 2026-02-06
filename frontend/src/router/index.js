import { createRouter, createWebHistory } from 'vue-router'

import DictsPage from '../views/DictsPage.vue'
import AiReviewPage from '../views/AiReviewPage.vue'
import QuestionVerifyPage from '../views/QuestionVerifyPage.vue'
import QuestionsPage from '../views/QuestionsPage.vue'
import PaperGeneratePage from '../views/PaperGeneratePage.vue'
import PapersManagePage from '../views/PapersManagePage.vue'
import AnswerSheetsPage from '../views/AnswerSheetsPage.vue'
import TextbooksPage from '../views/TextbooksPage.vue'
import LoginPage from '../views/LoginPage.vue'

import { getToken } from '../auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage },
    { path: '/', redirect: '/dicts' },
    { path: '/dicts', component: DictsPage, meta: { requiresAuth: true } },
    { path: '/ai-review', component: AiReviewPage, meta: { requiresAuth: true } },
    { path: '/question-verify', component: QuestionVerifyPage, meta: { requiresAuth: true } },
    { path: '/textbooks', component: TextbooksPage, meta: { requiresAuth: true } },
    { path: '/questions', component: QuestionsPage, meta: { requiresAuth: true } },
    { path: '/paper-generate', component: PaperGeneratePage, meta: { requiresAuth: true } },
    { path: '/papers', component: PapersManagePage, meta: { requiresAuth: true } },
    { path: '/answer-sheets', component: AnswerSheetsPage, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  if (to.path === '/login') {
    if (getToken()) return { path: '/dicts' }
    return true
  }
  if (to.meta?.requiresAuth && !getToken()) {
    return { path: '/login' }
  }
  return true
})
