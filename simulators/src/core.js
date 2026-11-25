import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import sky from '../assets/sky.hdr';
import sand_d from '../tex/sandstone_cracks_d.webp';
import sand_n from '../tex/sandstone_cracks_n.webp';
import cliff_d from '../tex/cliff_side_d.webp';
import cliff_n from '../tex/cliff_side_n.webp';
import coral_d from '../tex/coral_mud_01_d.webp';
import coral_n from '../tex/coral_mud_01_n.webp';
import marble_d from '../tex/marble_cliff_01_d.webp';
import marble_n from '../tex/marble_cliff_01_n.webp';
import rock_d from '../tex/rock_face_03_d.webp';
import rock_n from '../tex/rock_face_03_n.webp';
import grass_d from '../tex/aerial_grass_rock_d.webp';
import grass_n from '../tex/aerial_grass_rock_n.webp';

const SRC = { sand: [sand_d, sand_n], cliff: [cliff_d, cliff_n], coral: [coral_d, coral_n], marble: [marble_d, marble_n], rock: [rock_d, rock_n], grass: [grass_d, grass_n] };
const cache = {};
export function tex(name) {
  if (cache[name]) return cache[name];
  const [d, n] = SRC[name].map((u, i) => {
    const t = new THREE.TextureLoader().load(u);
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
    if (!i) t.colorSpace = THREE.SRGBColorSpace;
    return t;
  });
  return (cache[name] = { map: d, normalMap: n });
}
export const LEG = {
  sand: '#E8C872', shale: '#6B8E5A', limestone: '#7FB3D5', dense: '#8C7B6B', reef: '#F0A35E',
  oil: '#2E8B57', gas: '#E74C3C', water: '#3498DB', filtrate: '#9BD7F5', mud: '#7A6A58',
  SP: '#E74C3C', GR: '#2ECC71', RES: '#F1C40F', POR: '#3498DB', PRESSURE: '#00CEC9', measure: '#F1C40F', unc: '#95A5A6',
  text: '#ECEFF4', muted: '#8A96A3', panel: '#1A2129', bg: '#0F1419',
};

export class Stage {
  constructor(host) {
    this.host = host;
    const low = this.low = matchMedia('(max-width: 800px)').matches;
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: low, powerPreference: 'high-performance', preserveDrawingBuffer: true });
    r.setPixelRatio(Math.min(devicePixelRatio, low ? 1.5 : 1.75));
    r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 0.82;
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.localClippingEnabled = true;
    host.appendChild(r.domElement);
    this.css = new CSS2DRenderer(); this.css.domElement.className = 'labels'; host.appendChild(this.css.domElement);
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.3, 4000);
    this.controls = new OrbitControls(this.camera, r.domElement);
    Object.assign(this.controls, { enableDamping: true, dampingFactor: 0.07, maxPolarAngle: Math.PI * 0.56, enablePan: false });
    this.pmrem = new THREE.PMREMGenerator(r);
    const h = new RGBELoader().parse(sky.buffer.slice(sky.byteOffset, sky.byteOffset + sky.byteLength));
    const t = new THREE.DataTexture(h.data, h.width, h.height, THREE.RGBAFormat, h.type);
    t.colorSpace = THREE.LinearSRGBColorSpace; t.minFilter = t.magFilter = THREE.LinearFilter; t.flipY = true;
    t.mapping = THREE.EquirectangularReflectionMapping; t.needsUpdate = true;
    this.env = this.pmrem.fromEquirectangular(t).texture;
    const gc = document.createElement('canvas'); gc.width = 4; gc.height = 512; const gx = gc.getContext('2d'), gr = gx.createLinearGradient(0, 0, 0, 512);
    [[0, '#5f86a8'], [.42, '#a9c0d0'], [.58, '#cfd9de'], [1, '#8e9aa3']].forEach(([k, c]) => gr.addColorStop(k, c)); gx.fillStyle = gr; gx.fillRect(0, 0, 4, 512);
    this.skyTex = new THREE.CanvasTexture(gc); this.skyTex.colorSpace = THREE.SRGBColorSpace;
    this.composer = new EffectComposer(r, new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: low ? 0 : 4 }));
    this.renderPass = new RenderPass(new THREE.Scene(), this.camera);
    this.composer.addPass(this.renderPass);
    this.bloom = new UnrealBloomPass(new THREE.Vector2(4, 4), 0.16, 0.5, 0.92);
    if (!low) this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.reset();
    new ResizeObserver(() => this.resize()).observe(host);
    this.resize();
    this.clock = new THREE.Clock();
    r.setAnimationLoop(() => this.tick());
  }
  reset() {
    if (this.scene) this.scene.traverse(o => {
      if (o.isCSS2DObject) o.element.remove();
      if (o.geometry) o.geometry.dispose();
    });
    const s = this.scene = new THREE.Scene();
    s.environment = this.env; s.background = this.skyTex; s.backgroundIntensity = 0.8; s.environmentIntensity = 0.8;
    this.renderPass.scene = s;
    const sun = this.sun = new THREE.DirectionalLight('#fff0d8', 2.6);
    sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.06;
    s.add(sun, sun.target);
    this.cbs = []; this.fly = null;
    this.renderer.domElement.onclick = null;
  }
  setSun(pos, size) {
    this.sun.position.copy(pos);
    const c = this.sun.shadow.camera; c.left = c.bottom = -size; c.right = c.top = size; c.near = 1; c.far = pos.length() * 2.4; c.updateProjectionMatrix();
  }
  resize() {
    const w = this.host.clientWidth || 1, h = this.host.clientHeight || 1;
    this.renderer.setSize(w, h); this.composer.setSize(w, h); this.css.setSize(w, h);
    this.composer.setPixelRatio(this.renderer.getPixelRatio());
    this.camera.aspect = w / h; this.camera.fov = w / h < 1 ? 56 : 42; this.camera.updateProjectionMatrix();
  }
  view(pos, target, dur = 1.6) {
    const p = new THREE.Vector3(...pos), t = new THREE.Vector3(...target);
    if (!dur || this.reduced) { this.camera.position.copy(p); this.controls.target.copy(t); this.controls.update(); this.fly = null; return; }
    this.fly = { p0: this.camera.position.clone(), t0: this.controls.target.clone(), p, t, k: 0, dur };
  }
  tick() {
    const dt = Math.min(0.05, this.clock.getDelta());
    if (this.fly) {
      const f = this.fly; f.k = Math.min(1, f.k + dt / f.dur); const e = f.k * f.k * (3 - 2 * f.k);
      this.camera.position.lerpVectors(f.p0, f.p, e); this.controls.target.lerpVectors(f.t0, f.t, e);
      if (f.k >= 1) this.fly = null;
    }
    for (const c of this.cbs) c(dt);
    this.controls.update();
    this.composer.render();
    this.css.render(this.scene, this.camera);
  }
  // Подсказка над сценой: номер шага и что сделать сейчас.
  hint(i, steps) {
    const h = document.querySelector('#hint'), text = this.low ? steps[i].replace('вопрос справа', 'вопрос ниже') : steps[i]; h.hidden = false;
    h.innerHTML = `<b>Шаг ${i + 1} из ${steps.length}</b><span>${text}</span><i>${steps.map((_, k) => `<u class="${k < i ? 'was' : k === i ? 'now' : ''}"></u>`).join('')}</i>`;
  }
  label(text, pos, cls = '') {
    const e = document.createElement('div'); e.className = 'lbl ' + cls; e.innerHTML = text;
    const o = new CSS2DObject(e); o.position.set(...pos); return o;
  }
}

// Порода: фактура из фото, цвет из единой легенды, флюид точками в порах.
export function rockMaterial({ lith, color, fluid = null, fluid2 = null, scale = 0.12, inv = 0, pore = 1.6, reveal = 1, extra = {} }) {
  const name = { sand: 'sand', shale: 'cliff', dense: 'rock', limestone: 'marble', reef: 'coral' }[lith] || 'rock';
  const t = tex(name);
  const m = new THREE.MeshStandardMaterial({ ...t, normalScale: new THREE.Vector2(1.1, 1.1), roughness: 0.92, metalness: 0, side: THREE.DoubleSide, ...extra });
  m.userData.u = {
    uCol: { value: new THREE.Color(color || LEG[lith]) }, uReveal: { value: reveal }, uHasF: { value: fluid ? 1 : 0 },
    uF1: { value: new THREE.Color(fluid ? LEG[fluid] : '#000') }, uF2: { value: new THREE.Color(LEG[fluid2 || fluid] || '#000') },
    uInvC: { value: new THREE.Color(LEG.filtrate) }, uInv: { value: inv }, uScale: { value: scale }, uPore: { value: pore }, uHid: { value: tex('rock').map },
  };
  m.onBeforeCompile = s => {
    Object.assign(s.uniforms, m.userData.u);
    s.vertexShader = s.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;');
    s.fragmentShader = s.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vWP; uniform vec3 uCol,uF1,uF2,uInvC; uniform sampler2D uHid; uniform float uReveal,uHasF,uInv,uScale,uPore;
      float hh(vec3 p){p=fract(p*.3183099+.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
      vec2 cell(vec3 x){vec3 i=floor(x);float d=9.,id=0.;for(int a=-1;a<=1;a++)for(int b=-1;b<=1;b++)for(int c=-1;c<=1;c++){vec3 g=vec3(a,b,c);vec3 o=vec3(hh(i+g),hh(i+g+7.1),hh(i+g+3.7));float q=length(g+o-fract(x));if(q<d){d=q;id=hh(i+g+1.3);}}return vec2(d,id);}`)
      .replace('#include <map_fragment>', `
      vec3 tx=texture2D(map,vMapUv*uScale).rgb;
      vec3 hid=vec3(.20,.215,.235)*texture2D(uHid,vMapUv*uScale).rgb*1.35;
      vec3 rk=uCol*tx*1.08;
      if(uHasF>.5){ vec2 c=cell(vWP*uPore); float d=length(vWP.xz);
        vec3 fc=c.y<.5?uF1:uF2; if(d<uInv) fc=uInvC;
        float k=smoothstep(.40+.12*c.y,.26,c.x); rk=mix(rk,fc*.8,k*.85); }
      diffuseColor.rgb=mix(hid,rk,uReveal);`)
      .replace('#include <normal_fragment_maps>', `
      vec3 mapN=texture2D(normalMap,vNormalMapUv*uScale).xyz*2.-1.; mapN.xy*=normalScale*mix(.22,1.,uReveal);
      normal=normalize(tbn*mapN);`);
  };
  m.customProgramCacheKey = () => 'rock2';
  return m;
}
export const steel = (color = '#9aa3ab', rough = 0.35) => new THREE.MeshStandardMaterial({ color, metalness: 0.85, roughness: rough });
export const paint = (color, rough = 0.55) => new THREE.MeshStandardMaterial({ color, metalness: 0.15, roughness: rough });
export { THREE };
