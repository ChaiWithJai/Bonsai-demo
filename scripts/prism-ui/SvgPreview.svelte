<script lang="ts">
  import { browser } from '$app/environment';
  let {content = '', complete = false, validation}: {content?: string; complete?: boolean; validation?: {valid?: boolean; error?: string}} = $props();
  const preview = $derived.by(() => {
    if (content.length > 512000) return {status: 'Preview blocked: output exceeds the 512,000-character limit.', svg: ''};
    if (complete && validation?.valid === false) return {status: `SVG validation failed: ${validation.error || 'See original output.'}`, svg: ''};
    const start = content.search(/<svg\b/i);
    if (start < 0) return {status: complete ? 'No SVG document was generated.' : 'Waiting for SVG output.', svg: ''};
    const end = content.toLowerCase().indexOf('</svg>', start);
    if (end < start) return {status: complete ? 'Incomplete SVG: closing </svg> is missing. The output may have been truncated.' : 'SVG is still streaming; waiting for its closing tag.', svg: ''};
    if (!browser) return {status: 'Validating SVG…', svg: ''};
    const svg = content.slice(start, end + 6);
    if (/<!\s*(DOCTYPE|ENTITY)/i.test(content)) return {status: 'Preview blocked: document types and entity declarations are not allowed.', svg: ''};
    const document = new DOMParser().parseFromString(svg, 'image/svg+xml');
    if (document.querySelector('parsererror')) return {status: 'Malformed SVG XML. Inspect the original model output for details.', svg: ''};
    const root = document.documentElement;
    if (root.localName !== 'svg' || root.namespaceURI !== 'http://www.w3.org/2000/svg') return {status: 'Preview blocked: the SVG namespace is missing or invalid.', svg: ''};
    const elements = new Set(['svg','g','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','textPath','defs','title','desc','style','linearGradient','radialGradient','stop','clipPath','mask','pattern','use','symbol','marker','filter','feGaussianBlur','feOffset','feMerge','feMergeNode','feBlend','feColorMatrix','feComposite','feFlood','feDropShadow']);
    function unsafeCss(text: string) {
      if (/\\|@import|@font-face|expression\s*\(|javascript\s*:/i.test(text)) return true;
      return /url\s*\(/i.test(text.replace(/url\(\s*(['"]?)#[A-Za-z_][\w:.-]*\1\s*\)/gi, ''));
    }
    const nodes = Array.from(document.querySelectorAll('*'));
    if (nodes.length > 10000) return {status: 'Preview blocked: SVG exceeds the 10,000-element limit.', svg: ''};
    for (const element of nodes) {
      if (!elements.has(element.localName) || element.namespaceURI !== root.namespaceURI) return {status: `Preview blocked: unsupported element <${element.localName}>. Original output is unchanged.`, svg: ''};
      if (element.localName === 'style' && unsafeCss(element.textContent || '')) return {status: 'Preview blocked: external or unsafe CSS. Original output is unchanged.', svg: ''};
      for (const attribute of Array.from(element.attributes)) {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim();
        if (name.startsWith('on') || name === 'xml:base' || name === 'src' || ((name === 'href' || name.endsWith(':href')) && !/^#[A-Za-z_][\w:.-]*$/.test(value)) || unsafeCss(value)) return {status: `Preview blocked: unsafe or external reference in ${attribute.name}. Original output is unchanged.`, svg: ''};
      }
    }
    return {status: 'SVG validated for isolated image preview. Original SVG is unchanged.', svg};
  });
  const imageUrl = $derived(preview.svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(preview.svg)}` : '');
</script>
<section class="svg-preview" aria-label="Generated SVG preview">
  <p class="svg-status" role="status">{preview.status}</p>
  {#if imageUrl}<img src={imageUrl} alt="Model-generated SVG of a pelican riding a bicycle"/><a href={imageUrl} download="pelican-bicycle.svg">Download validated original SVG</a>{/if}
  <p class="svg-note">Model output rendered as an isolated image. Preview validation checks structure and references, not drawing quality.</p>
</section>
<style>
.svg-preview{border:1px solid var(--border);border-radius:13px;padding:15px;margin:12px 0;background:var(--card)}.svg-status,.svg-note{font-size:11px;line-height:1.5;color:var(--muted-foreground)}img{display:block;width:100%;height:360px;object-fit:contain;background:#fff;border-radius:9px;margin:14px 0}a{display:inline-block;font-size:12px;text-decoration:underline}.svg-note{margin-top:12px}@media(max-width:767px){img{height:280px}}
</style>
