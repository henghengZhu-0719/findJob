import DOMPurify from 'dompurify'

/** 原站正文多是 Word 导出的 HTML：内联字体来自站点私有 ttf，本地没有；
 *  字号用 pt 且忽大忽小。这里把字体族丢掉、字号收敛成相对层级，交给 CSS 统一排版。 */
function normalizeStyle(el) {
  const style = el.getAttribute('style')
  if (!style) return

  const kept = []
  for (const decl of style.split(';')) {
    const [rawProp, ...rest] = decl.split(':')
    if (!rawProp || !rest.length) continue
    const prop = rawProp.trim().toLowerCase()
    const val = rest.join(':').trim()

    // 字体族、行高、颜色一律交给页面样式，避免本地缺字体导致错版
    if (['font-family', 'line-height', 'color', 'background', 'background-color'].includes(prop)) {
      continue
    }
    if (prop === 'font-size') {
      const m = /^([\d.]+)\s*(pt|px)$/.exec(val)
      if (!m) continue
      const px = m[2] === 'pt' ? parseFloat(m[1]) * 1.333 : parseFloat(m[1])
      // 只保留“明显是标题”的层级，正文字号统一由 CSS 决定
      if (px >= 24) kept.push('font-size:1.5em')
      else if (px >= 19) kept.push('font-size:1.25em')
      else if (px >= 17) kept.push('font-size:1.1em')
      continue
    }
    kept.push(`${prop}:${val}`)
  }

  if (kept.length) el.setAttribute('style', kept.join(';'))
  else el.removeAttribute('style')
}

/**
 * 消毒 + 规范化原站正文 HTML。
 * @param {string} html  原始 content_html
 * @param {string} baseUrl  该公告的原文地址，用于把相对路径补成绝对地址
 */
export function sanitizeContent(html, baseUrl) {
  if (!html) return ''

  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    // 相对路径的图片/链接在 localhost 下会 404，按原文地址补全
    for (const attr of ['src', 'href']) {
      const v = node.getAttribute?.(attr)
      if (v && !/^(https?:|data:|#|mailto:)/i.test(v)) {
        try {
          node.setAttribute(attr, new URL(v, baseUrl).href)
        } catch {
          /* 地址实在解析不了就原样留着 */
        }
      }
    }
    if (node.tagName === 'A') {
      node.setAttribute('target', '_blank')
      node.setAttribute('rel', 'noreferrer noopener')
    }
    if (node.tagName === 'IMG') {
      node.setAttribute('loading', 'lazy')
      node.removeAttribute('width')
      node.removeAttribute('height')
    }
    normalizeStyle(node)
  })

  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'p', 'br', 'div', 'span', 'strong', 'b', 'em', 'i', 'u', 's', 'sub', 'sup',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'hr',
      'ul', 'ol', 'li', 'dl', 'dt', 'dd',
      'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'caption', 'colgroup', 'col',
      'a', 'img', 'figure', 'figcaption', 'pre', 'code',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'target', 'rel', 'loading',
                   'style', 'align', 'colspan', 'rowspan', 'start', 'type', 'class'],
    ALLOWED_URI_REGEXP: /^(?:https?|mailto|data:image\/)/i,
  })

  DOMPurify.removeHook('afterSanitizeAttributes')

  // 宽表格包一层滚动容器，避免撑破抽屉
  const doc = new DOMParser().parseFromString(clean, 'text/html')
  doc.querySelectorAll('table').forEach((t) => {
    const wrap = doc.createElement('div')
    wrap.className = 'table-scroll'
    t.replaceWith(wrap)
    wrap.appendChild(t)
  })
  return doc.body.innerHTML
}
