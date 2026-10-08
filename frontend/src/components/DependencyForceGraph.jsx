import React, { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceX, forceY, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { drag } from 'd3-drag'
import { zoom, zoomIdentity } from 'd3-zoom'

// Read the active theme's colours from the CSS variables so the graph is readable in
// both light and dark mode (SVG attributes cannot use var() directly in every case).
function readTheme() {
  const css = getComputedStyle(document.documentElement)
  const v = (name, fallback) => css.getPropertyValue(name).trim() || fallback
  return {
    text: v('--text', '#16181D'),
    faint: v('--text-faint', '#8B909A'),
    surface: v('--surface', '#FFFFFF'),
    accent: v('--accent', '#0F6E66'),
    ok: v('--ok', '#2E7D4F'),
    warn: v('--warn', '#A86B00'),
    err: v('--err', '#B42318'),
  }
}

const LABEL_CHAR_WIDTH = 7.4 // approx. width of one 12px monospace character

export default function DependencyForceGraph({ nodes, edges, onNavigateToFile }) {
  const containerRef = useRef(null)
  const fitRef = useRef(() => {})
  const navigateRef = useRef(onNavigateToFile)
  navigateRef.current = onNavigateToFile
  const [hoveredNode, setHoveredNode] = useState(null)
  const [themeKey, setThemeKey] = useState(() => document.documentElement.getAttribute('data-theme'))

  // Redraw when the user toggles light/dark.
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeKey(document.documentElement.getAttribute('data-theme')))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return

    const colors = readTheme()
    const typeColors = {
      class: colors.accent,
      interface: colors.accent,
      enum: colors.accent,
      record: colors.accent,
      method: colors.ok,
      constructor: colors.ok,
      function: colors.warn,
    }

    const width = containerRef.current.clientWidth || 800
    const height = 600

    // d3-force mutates node/link objects; work on copies so React props stay untouched.
    const nodeData = nodes.map((n) => ({ ...n }))
    const nodeById = new Map(nodeData.map((n) => [n.id, n]))
    const linkData = edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ ...e }))

    const svg = select(containerRef.current)
      .append('svg')
      .attr('width', '100%')
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .style('display', 'block')

    svg
      .append('defs')
      .append('marker')
      .attr('id', 'dep-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', colors.faint)

    const g = svg.append('g')

    // Wheel zooms only with Ctrl held, so scrolling the page over the graph still scrolls the page.
    const zoomBehavior = zoom()
      .scaleExtent([0.1, 4])
      .filter((event) => (event.type === 'wheel' ? event.ctrlKey : !event.ctrlKey) && !event.button)
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoomBehavior).on('dblclick.zoom', null)

    // Scale and centre every node and its label inside the box.
    const fitToView = (animate = true) => {
      const padding = 40
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const d of nodeData) {
        minX = Math.min(minX, d.x - 12)
        maxX = Math.max(maxX, d.x + 16 + d.label.length * LABEL_CHAR_WIDTH)
        minY = Math.min(minY, d.y - 12)
        maxY = Math.max(maxY, d.y + 12)
      }
      if (minX === Infinity) return
      const boxW = maxX - minX
      const boxH = maxY - minY
      const scale = Math.min((width - 2 * padding) / boxW, (height - 2 * padding) / boxH, 1.5)
      const tx = (width - boxW * scale) / 2 - minX * scale
      const ty = (height - boxH * scale) / 2 - minY * scale
      const target = zoomIdentity.translate(tx, ty).scale(scale)
      if (animate) svg.transition().duration(400).call(zoomBehavior.transform, target)
      else svg.call(zoomBehavior.transform, target)
    }
    fitRef.current = () => fitToView(true)
    svg.on('dblclick', () => fitToView(true))

    const link = g
      .append('g')
      .attr('stroke', colors.faint)
      .attr('stroke-opacity', 0.75)
      .attr('stroke-width', 1.5)
      .selectAll('line')
      .data(linkData)
      .join('line')
      .attr('marker-end', 'url(#dep-arrow)')

    const node = g
      .append('g')
      .selectAll('g')
      .data(nodeData)
      .join('g')
      .style('cursor', 'grab')

    node.append('circle')
      .attr('r', 8)
      .attr('fill', (d) => typeColors[d.type] || colors.faint)
      .attr('stroke', (d) => (d.has_docstring ? colors.ok : colors.err))
      .attr('stroke-width', 2)

    // Names are always visible; a surface-coloured halo keeps them legible over edges.
    node
      .append('text')
      .text((d) => d.label)
      .attr('x', 14)
      .attr('y', 4)
      .attr('fill', colors.text)
      .attr('stroke', colors.surface)
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
      .attr('paint-order', 'stroke')
      .attr('font-size', '12px')
      .attr('font-family', '"IBM Plex Mono", monospace')
      .attr('font-weight', 500)
      .style('pointer-events', 'none')

    const paint = () => {
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)
      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
    }

    // Spread by label length so names do not overlap; pull gently toward the middle.
    const simulation = forceSimulation(nodeData)
      .force('link', forceLink(linkData).id((d) => d.id).distance(100))
      .force('charge', forceManyBody().strength(-240))
      .force('x', forceX(width / 2).strength(0.1))
      .force('y', forceY(height / 2).strength(0.14))
      .force('collide', forceCollide((d) => 16 + d.label.length * 3.2))
      .stop()

    // Settle fully before the first paint, then fit with no animation, so the graph
    // appears already centred and complete instead of drifting after it is drawn.
    simulation.tick(400)
    paint()
    fitToView(false)

    // After the initial layout the simulation only runs while a node is being dragged.
    simulation.on('tick', paint)

    node.call(
      drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.1).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )

    node.on('mouseenter', (event, d) => setHoveredNode(d))
    node.on('mouseleave', () => setHoveredNode(null))
    node.on('click', (event, d) => {
      if (navigateRef.current) navigateRef.current(d.file)
    })

    return () => {
      simulation.stop()
      select(containerRef.current).select('svg').remove()
    }
  }, [nodes, edges, themeKey])

  return (
    <div style={{ position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '600px', cursor: 'grab' }} />

      <div className="graph-controls">
        <button className="secondary fit-btn" style={{ padding: '0 8px', fontSize: '0.75rem' }} onClick={() => fitRef.current()}>
          Fit to view
        </button>
      </div>
      <div style={{ position: 'absolute', left: 16, bottom: 12, fontSize: '0.6875rem', color: 'var(--text-faint)', pointerEvents: 'none' }}>
        Drag to pan · Ctrl + scroll to zoom · Double-click to fit
      </div>

      {hoveredNode && (
        <div style={{
          position: 'absolute',
          top: 16,
          left: 16,
          backgroundColor: 'var(--surface)',
          padding: '12px',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          pointerEvents: 'none'
        }}>
          <div style={{ fontFamily: '"IBM Plex Mono", monospace', fontWeight: 600, marginBottom: '4px' }}>
            {hoveredNode.label}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Type: {hoveredNode.type}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            File: {hoveredNode.file}
          </div>
          <div style={{ fontSize: '0.75rem', color: hoveredNode.has_docstring ? 'var(--ok)' : 'var(--err)', marginTop: '4px', fontWeight: 500 }}>
            {hoveredNode.has_docstring ? 'Documented' : 'Needs documentation'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-faint)', marginTop: '8px' }}>
            Click to view in changes
          </div>
        </div>
      )}
    </div>
  )
}
