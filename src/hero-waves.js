(()=>{
'use strict';
const hero=document.querySelector('.hero-waves'),canvas=hero?.querySelector('canvas'),button=hero?.querySelector('.wave-toggle'),reduce=matchMedia('(prefers-reduced-motion:reduce)');
if(!canvas)return;
const ctx=canvas.getContext('2d');
if(!ctx)return;
let image,points=[],phase=0,last=0,frame=0,visible=true,paused=reduce.matches,opacity=.08,boost=0,scrollPosition=scrollY,scrollTime=performance.now();
const smooth=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t)};
function prepare(){
 const rect=hero.getBoundingClientRect();
 canvas.width=Math.min(680,Math.round(rect.width/2));
 canvas.height=Math.max(1,Math.round(canvas.width*rect.height/rect.width));
 image=ctx.createImageData(canvas.width,canvas.height);points=[];
 const w=canvas.width,h=canvas.height;
 // Two coherent circular sources above and below the portrait's center.
 // The displayed field is Re[exp(i(kr1-wt))+exp(i(kr2-wt))], not a scrolling sine curve.
 const sx=w*.98,y1=h*.26,y2=h*.74,k=2*Math.PI/(w*.105);
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const d1=Math.hypot(x-sx,y-y1),d2=Math.hypot(x-sx,y-y2),nx=x/w,ny=y/h;
  // A soft clear area protects the text. Ripples remain along the top, lower edge and portrait margin.
  const textZone=(1-smooth(.47,.66,nx))*smooth(.10,.25,ny)*(1-smooth(.70,.91,ny));
  const edge=smooth(0,.06,nx)*(1-smooth(.94,1,nx))*smooth(0,.08,ny)*(1-smooth(.91,1,ny));
  const envelope=edge*(1-.96*textZone)*Math.min(1,Math.sqrt(w*.40/Math.max(w*.20,(d1+d2)/2)));
  points.push([k*d1,k*d2,envelope]);
 }
 paint();
}
function paint(){
 const pixels=image.data;
 for(let i=0;i<points.length;i++){
  const [a,b,envelope]=points[i],amplitude=(Math.cos(a-phase)+Math.cos(b-phase))*.5;
  const color=amplitude>0?[162,84,31]:[70,104,116],j=i*4;
  pixels[j]=color[0];pixels[j+1]=color[1];pixels[j+2]=color[2];
  pixels[j+3]=Math.round(255*opacity*envelope*Math.pow(Math.abs(amplitude),1.5));
 }
 ctx.putImageData(image,0,0);canvas.dataset.phase=phase.toFixed(3);
}
function labels(){button.hidden=reduce.matches;button.textContent=paused?'Play background':'Pause background';button.setAttribute('aria-pressed',String(paused))}
function tick(now){frame=0;if(paused||!visible||document.hidden||reduce.matches){last=0;return}if(!last)last=now;if(now-last>=45){const elapsed=Math.min(now-last,100);boost*=Math.exp(-elapsed/600);phase+=elapsed*.00060*(1+boost);last=now;paint()}frame=requestAnimationFrame(tick)}
function kick(){labels();if(!frame&&!paused&&visible&&!document.hidden&&!reduce.matches){last=0;frame=requestAnimationFrame(tick)}}
button.addEventListener('click',()=>{paused=!paused;kick()});
addEventListener('scroll',()=>{const now=performance.now(),delta=Math.abs(scrollY-scrollPosition),elapsed=Math.max(16,now-scrollTime);if(visible&&!paused&&!reduce.matches)boost=Math.min(1.5,boost+delta/elapsed*.18);scrollPosition=scrollY;scrollTime=now},{passive:true});
new ResizeObserver(prepare).observe(hero);
new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;kick()},{threshold:.01}).observe(hero);
document.addEventListener('visibilitychange',kick);reduce.addEventListener('change',()=>{paused=reduce.matches;paint();kick()});
prepare();kick();
})();
