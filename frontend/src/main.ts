import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import GlassButton from './components/GlassButton.vue'
import GlassInput from './components/GlassInput.vue'
import GlassSwitch from './components/GlassSwitch.vue'
import GlassSlider from './components/GlassSlider.vue'
import GlassPanel from './components/GlassPanel.vue'
import GlassDialog from './components/GlassDialog.vue'
import GlassSegmented from './components/GlassSegmented.vue'
import router from './router'
import './liquid-glass-core.css'
import './liquid-glass-light.css'
import './style.css'

const app = createApp(App)

// 全局注册 Element-Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 全局注册液态玻璃组件（使用 @sapryniukt/vue-liquid-glass 开源库）
app.component('GlassButton', GlassButton)
app.component('GlassInput', GlassInput)
app.component('GlassSwitch', GlassSwitch)
app.component('GlassSlider', GlassSlider)
app.component('GlassPanel', GlassPanel)
app.component('GlassDialog', GlassDialog)
app.component('GlassSegmented', GlassSegmented)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
