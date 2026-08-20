/* ============================================================
   Liquid Glass WebGL Background — 真实光线折射效果
   ============================================================
   参考 iyinchao/liquid-glass-studio 的 WebGL2 实现原理
   - 彩色渐变背景 + 多个模糊光源
   - 噪声函数扰动 UV，模拟光线折射扭曲
   - 缓慢的时间动画，模拟液体流动
   - 轻量级实现，60fps 流畅运行
   ============================================================ */

(function() {
  'use strict';

  // 顶点着色器：全屏四边形
  const vertexShaderSource = `#version 300 es
    in vec2 a_position;
    out vec2 v_uv;
    void main() {
      v_uv = a_position * 0.5 + 0.5;
      gl_Position = vec4(a_position, 0.0, 1.0);
    }
  `;

  // 片段着色器：液态玻璃折射背景
  const fragmentShaderSource = `#version 300 es
    precision highp float;

    in vec2 v_uv;
    out vec4 fragColor;

    uniform float u_time;
    uniform vec2 u_resolution;
    uniform vec2 u_mouse;

    // 简单的 2D 噪声函数
    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }

    float noise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      float a = hash(i);
      float b = hash(i + vec2(1.0, 0.0));
      float c = hash(i + vec2(0.0, 1.0));
      float d = hash(i + vec2(1.0, 1.0));
      return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
    }

    // 分形布朗运动（多层噪声叠加）
    float fbm(vec2 p) {
      float value = 0.0;
      float amplitude = 0.5;
      float frequency = 1.0;
      for (int i = 0; i < 5; i++) {
        value += amplitude * noise(p * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
      }
      return value;
    }

    // 模糊圆形光源
    float blob(vec2 uv, vec2 center, float radius, float blur) {
      float dist = distance(uv, center);
      return smoothstep(radius + blur, radius - blur, dist);
    }

    void main() {
      vec2 uv = v_uv;
      vec2 aspect = vec2(u_resolution.x / u_resolution.y, 1.0);
      vec2 p = (uv - 0.5) * aspect;

      // 时间动画（缓慢流动）
      float t = u_time * 0.08;

      // 用噪声扰动 UV，模拟光线折射扭曲
      float noiseScale = 3.0;
      vec2 distort = vec2(
        fbm(p * noiseScale + vec2(t, t * 0.7)),
        fbm(p * noiseScale + vec2(t * 0.8, -t * 0.5))
      );
      distort = (distort - 0.5) * 0.06; // 扭曲强度
      vec2 refractedUV = uv + distort;

      // 基础彩色渐变（多色渐变）
      vec3 color1 = vec3(0.85, 0.92, 1.0);  // 浅蓝
      vec3 color2 = vec3(0.94, 0.88, 1.0);  // 浅紫
      vec3 color3 = vec3(1.0, 0.88, 0.94);  // 浅粉
      vec3 color4 = vec3(1.0, 0.95, 0.82);  // 浅黄
      vec3 color5 = vec3(0.85, 0.97, 0.90);  // 浅绿

      // 用扰动后的 UV 做渐变混合
      float gradient = refractedUV.x * 0.5 + refractedUV.y * 0.5;
      vec3 baseColor = mix(color1, color3, smoothstep(0.0, 0.5, gradient));
      baseColor = mix(baseColor, color5, smoothstep(0.3, 0.8, refractedUV.y));

      // 多个模糊彩色光源（模拟光线透过玻璃）
      vec2 blob1Pos = vec2(0.2 + sin(t * 0.5) * 0.1, 0.3 + cos(t * 0.3) * 0.1);
      vec2 blob2Pos = vec2(0.8 + cos(t * 0.4) * 0.1, 0.7 + sin(t * 0.6) * 0.1);
      vec2 blob3Pos = vec2(0.6 + sin(t * 0.3 + 1.0) * 0.15, 0.2 + cos(t * 0.5 + 0.5) * 0.1);
      vec2 blob4Pos = vec2(0.3 + cos(t * 0.4 + 2.0) * 0.1, 0.8 + sin(t * 0.3 + 1.5) * 0.15);

      // 应用折射扭曲到光源位置
      blob1Pos += distort * 0.5;
      blob2Pos += distort * 0.5;
      blob3Pos += distort * 0.5;
      blob4Pos += distort * 0.5;

      float b1 = blob(uv, blob1Pos, 0.25, 0.2);
      float b2 = blob(uv, blob2Pos, 0.3, 0.25);
      float b3 = blob(uv, blob3Pos, 0.2, 0.18);
      float b4 = blob(uv, blob4Pos, 0.22, 0.2);

      // 光源颜色（高饱和度，模拟光线）
      vec3 light1 = vec3(0.4, 0.7, 1.0);   // 蓝
      vec3 light2 = vec3(1.0, 0.5, 0.8);   // 粉
      vec3 light3 = vec3(0.5, 1.0, 0.7);   // 绿
      vec3 light4 = vec3(1.0, 0.8, 0.4);   // 黄

      // 叠加光源到基础色
      baseColor += light1 * b1 * 0.4;
      baseColor += light2 * b2 * 0.35;
      baseColor += light3 * b3 * 0.3;
      baseColor += light4 * b4 * 0.25;

      // 添加细微的折射条纹（模拟玻璃的棱镜效应）
      float prism = sin((refractedUV.x + refractedUV.y) * 30.0 + t * 2.0) * 0.5 + 0.5;
      vec3 prismColor = mix(
        vec3(1.0, 0.95, 0.9),
        vec3(0.9, 0.95, 1.0),
        prism
      );
      baseColor = mix(baseColor, prismColor, 0.08);

      // 鼠标交互：鼠标位置添加额外的折射焦点
      vec2 mouseUV = u_mouse / u_resolution;
      mouseUV.y = 1.0 - mouseUV.y;
      float mouseFocus = blob(uv, mouseUV, 0.15, 0.1);
      baseColor += vec3(1.0, 1.0, 1.0) * mouseFocus * 0.15;

      // 整体亮度和饱和度调整
      baseColor = pow(baseColor, vec3(0.95)); // 轻微伽马校正
      baseColor = clamp(baseColor, 0.0, 1.0);

      fragColor = vec4(baseColor, 1.0);
    }
  `;

  // 编译着色器
  function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compile error:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function createProgram(gl, vertexShader, fragmentShader) {
    const program = gl.createProgram();
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program));
      return null;
    }
    return program;
  }

  // 初始化 WebGL
  function init() {
    const canvas = document.getElementById('liquid-glass-bg');
    if (!canvas) {
      console.warn('Liquid glass background canvas not found');
      return;
    }

    const gl = canvas.getContext('webgl2', {
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance'
    });

    if (!gl) {
      console.warn('WebGL2 not supported, falling back to CSS background');
      canvas.style.display = 'none';
      return;
    }

    // 编译着色器
    const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexShaderSource);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentShaderSource);
    if (!vertexShader || !fragmentShader) return;

    const program = createProgram(gl, vertexShader, fragmentShader);
    if (!program) return;

    // 创建全屏四边形
    const positions = new Float32Array([
      -1, -1,  1, -1,  -1, 1,
      -1,  1,  1, -1,   1, 1
    ]);

    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const positionLoc = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(positionLoc);
    gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);

    // 获取 uniform 位置
    const timeLoc = gl.getUniformLocation(program, 'u_time');
    const resolutionLoc = gl.getUniformLocation(program, 'u_resolution');
    const mouseLoc = gl.getUniformLocation(program, 'u_mouse');

    // 鼠标位置
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;

    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
    });

    // 调整画布大小
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2); // 限制 DPR 提升性能
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = window.innerWidth + 'px';
      canvas.style.height = window.innerHeight + 'px';
      gl.viewport(0, 0, canvas.width, canvas.height);
    }

    window.addEventListener('resize', resize);
    resize();

    // 渲染循环
    const startTime = performance.now();
    let lastTime = 0;
    let frameCount = 0;

    function render(now) {
      const time = (now - startTime) / 1000;

      // 帧率控制（目标 60fps，但允许降频）
      const delta = time - lastTime;
      if (delta < 0.014) { // ~70fps 上限
        requestAnimationFrame(render);
        return;
      }
      lastTime = time;
      frameCount++;

      gl.useProgram(program);

      // 更新 uniform
      gl.uniform1f(timeLoc, time);
      gl.uniform2f(resolutionLoc, canvas.width, canvas.height);
      gl.uniform2f(mouseLoc, mouseX * (canvas.width / window.innerWidth), mouseY * (canvas.height / window.innerHeight));

      // 绘制
      gl.drawArrays(gl.TRIANGLES, 0, 6);

      requestAnimationFrame(render);
    }

    requestAnimationFrame(render);

    // 页面可见性变化时暂停/恢复（节省性能）
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        // 暂停渲染（通过标记）
        canvas.dataset.paused = 'true';
      } else {
        canvas.dataset.paused = 'false';
      }
    });

    console.log('Liquid glass WebGL background initialized');
  }

  // DOM 加载完成后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
