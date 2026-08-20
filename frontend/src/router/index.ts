import { createRouter, createWebHashHistory } from 'vue-router'
import { useActivationStore } from '@/stores/activation'

/**
 * 使用 hash 路由:生产模式下由 FastAPI 单进程托管,
 * hash 模式避免 history 模式需要的服务端 fallback 配置。
 */
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'main',
      component: () => import('@/views/MainLayout.vue'),
    },
    {
      path: '/mobile',
      name: 'mobile',
      component: () => import('@/views/MobileScannerPage.vue'),
    },
    {
      path: '/print',
      name: 'print',
      component: () => import('@/views/PrintReportPage.vue'),
    },
    {
      path: '/activation',
      name: 'activation',
      component: () => import('@/views/ActivationPage.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

// 激活守卫:除激活页外,未激活一律跳转激活页
// 注意:/mobile(手机扫码)与 /print(打印)为白名单页面,与后端激活守卫一致
router.beforeEach(async (to) => {
  if (to.name === 'activation' || to.name === 'mobile' || to.name === 'print') return true
  const store = useActivationStore()
  if (!store.checked) {
    await store.checkStatus()
  }
  if (!store.activated) {
    return { name: 'activation' }
  }
  return true
})

export default router
