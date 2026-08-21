<template>
  <LiquidGlassPanel
    :border-radius="borderRadius"
    :bezel-width="bezelWidth"
    :glass-thickness="glassThickness"
    :refractive-index="refractiveIndex"
    :blur="blur"
    :scale-ratio="scaleRatio"
    :specular-opacity="specularOpacity"
    :specular-saturation="specularSaturation"
    :magnify="magnify"
    :magnifying-scale="magnifyingScale"
    :background-opacity="backgroundOpacity"
    :shadow="shadow"
    :content-padding="contentPadding"
    :hover-refractive-boost="hoverRefractiveBoost"
    :hover-light="hoverLight"
    class="glass-panel-wrapper"
  >
    <slot></slot>
  </LiquidGlassPanel>
</template>

<script setup lang="ts">
import { LiquidGlassPanel } from '@sapryniukt/vue-liquid-glass'

interface Props {
  borderRadius?: number
  bezelWidth?: number
  glassThickness?: number
  refractiveIndex?: number
  blur?: number
  scaleRatio?: number
  specularOpacity?: number
  specularSaturation?: number
  magnify?: boolean
  magnifyingScale?: number
  backgroundOpacity?: number
  shadow?: string
  contentPadding?: string
  hoverRefractiveBoost?: number
  hoverLight?: boolean
}

withDefaults(defineProps<Props>(), {
  borderRadius: 24,
  bezelWidth: 2,
  glassThickness: 3,
  refractiveIndex: 1.5,
  blur: 20,
  scaleRatio: 1.1,
  specularOpacity: 0.6,
  specularSaturation: 1.5,
  magnify: false,
  magnifyingScale: 1.1,
  backgroundOpacity: 0.4,
  shadow: '0 8px 24px rgba(90, 110, 140, 0.1)',
  contentPadding: '20px',
  hoverRefractiveBoost: 0.2,
  hoverLight: true,
})
</script>

<style scoped>
.glass-panel-wrapper {
  width: 100%;
}
</style>
