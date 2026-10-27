/* Runs before first paint: apply saved theme (external file so the CSP can stay strict). */
try{var t=localStorage.getItem("navs-theme");if(!t&&window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches)t="dark";if(t==="dark")document.documentElement.dataset.theme="dark"}catch(e){}
