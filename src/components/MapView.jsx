import { useRef, useState, useEffect, useCallback } from 'react'
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'
import CommentCard from './CommentCard'
import HintBar from './HintBar'
import locations from '../data/locations.json'
import './MapView.css'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN

// Build GeoJSON from locations data
const geojson = {
  type: 'FeatureCollection',
  features: locations.map((loc) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [loc.lng, loc.lat] },
    properties: {
      id: loc.id,
      city: loc.city,
      country: loc.country,
      region: loc.region,
      upvotes: loc.posts.reduce((sum, p) => sum + p.upvotes, 0),
    },
  })),
}

// Layer styles
const clusterLayer = {
  id: 'clusters',
  type: 'circle',
  source: 'locations',
  filter: ['has', 'point_count'],
  paint: {
    'circle-color': [
      'step', ['get', 'point_count'],
      '#FF6B35', 5,
      '#FF5722', 10,
      '#E64A19',
    ],
    'circle-radius': [
      'step', ['get', 'point_count'],
      22, 5, 28, 10, 34,
    ],
    'circle-opacity': 0.9,
    'circle-stroke-width': 2,
    'circle-stroke-color': 'rgba(255, 107, 53, 0.3)',
  },
}

const clusterCountLayer = {
  id: 'cluster-count',
  type: 'symbol',
  source: 'locations',
  filter: ['has', 'point_count'],
  layout: {
    'text-field': '{point_count_abbreviated}',
    'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
    'text-size': 13,
  },
  paint: {
    'text-color': '#ffffff',
  },
}

const unclusteredPointLayer = {
  id: 'unclustered-point',
  type: 'circle',
  source: 'locations',
  filter: ['!', ['has', 'point_count']],
  paint: {
    'circle-color': '#FF6B35',
    'circle-radius': 7,
    'circle-opacity': 0.95,
    'circle-stroke-width': 2,
    'circle-stroke-color': 'rgba(255, 107, 53, 0.35)',
    'circle-blur': 0,
  },
}

// Fog / atmosphere
const FOG_DARK = {
  color: 'rgb(15, 15, 35)',
  'high-color': 'rgb(20, 20, 50)',
  'horizon-blend': 0.08,
  'space-color': 'rgb(10, 10, 25)',
  'star-intensity': 0.6,
}

const FOG_LIGHT = {
  color: 'rgb(240, 234, 224)',
  'high-color': 'rgb(200, 215, 230)',
  'horizon-blend': 0.05,
  'space-color': 'rgb(180, 200, 220)',
  'star-intensity': 0.0,
}

const INITIAL_VIEW = {
  longitude: 10,
  latitude: 20,
  zoom: 1.8,
  pitch: 0,
  bearing: 0,
}

export default function MapView({ theme = 'dark' }) {
  const mapRef = useRef(null)
  const rotationRef = useRef(null)
  const idleTimerRef = useRef(null)

  const [viewState, setViewState] = useState(INITIAL_VIEW)
  const [popupInfo, setPopupInfo] = useState(null) // { location, lng, lat }
  const [isUserInteracting, setIsUserInteracting] = useState(false)
  const [mapInteracted, setMapInteracted] = useState(false)
  const [mapLoaded, setMapLoaded] = useState(false)

  // ── Auto-rotation ─────────────────────────────────────────
  const startRotation = useCallback(() => {
    if (rotationRef.current) return
    rotationRef.current = setInterval(() => {
      setViewState((prev) => {
        if (prev.zoom >= 4) return prev
        return { ...prev, longitude: prev.longitude + 0.08 }
      })
    }, 30)
  }, [])

  const stopRotation = useCallback(() => {
    if (rotationRef.current) {
      clearInterval(rotationRef.current)
      rotationRef.current = null
    }
  }, [])

  // Start rotating once map loads
  useEffect(() => {
    if (mapLoaded) {
      const t = setTimeout(startRotation, 800)
      return () => clearTimeout(t)
    }
  }, [mapLoaded, startRotation])

  // Stop/resume rotation on interaction
  useEffect(() => {
    if (isUserInteracting) {
      stopRotation()
    } else {
      // Resume after 3s idle
      idleTimerRef.current = setTimeout(() => {
        if (viewState.zoom < 4) startRotation()
      }, 3000)
    }
    return () => clearTimeout(idleTimerRef.current)
  }, [isUserInteracting, stopRotation, startRotation, viewState.zoom])

  // Stop rotation when zoomed in
  useEffect(() => {
    if (viewState.zoom >= 4) stopRotation()
  }, [viewState.zoom, stopRotation])

  // Cleanup on unmount
  useEffect(() => () => {
    stopRotation()
    clearTimeout(idleTimerRef.current)
  }, [stopRotation])

  // ── Interaction handlers ──────────────────────────────────
  const handleInteractionStart = () => {
    setIsUserInteracting(true)
    setMapInteracted(true)
  }

  const handleInteractionEnd = () => {
    setIsUserInteracting(false)
  }

  const handleClick = useCallback((e) => {
    const map = mapRef.current?.getMap()
    if (!map) return

    const features = map.queryRenderedFeatures(e.point, {
      layers: ['clusters', 'unclustered-point'],
    })

    if (!features.length) {
      setPopupInfo(null)
      return
    }

    const feature = features[0]

    // Cluster click → zoom to expand
    if (feature.layer.id === 'clusters') {
      const clusterId = feature.properties.cluster_id
      map.getSource('locations').getClusterExpansionZoom(clusterId, (err, zoom) => {
        if (err) return
        map.easeTo({
          center: feature.geometry.coordinates,
          zoom: zoom + 0.5,
          duration: 600,
        })
      })
      return
    }

    // Marker click → find location data and open popup
    const locId = feature.properties.id
    const location = locations.find((l) => l.id === locId)
    if (!location) return

    const [lng, lat] = feature.geometry.coordinates.slice()

    // Fly to marker
    map.flyTo({
      center: [lng, lat],
      zoom: Math.max(map.getZoom(), 4),
      duration: 800,
      essential: true,
    })

    setPopupInfo({ location, lng, lat })
  }, [])

  // Cursor management
  const handleMouseEnter = useCallback(() => {
    const map = mapRef.current?.getMap()
    if (map) map.getCanvas().style.cursor = 'pointer'
  }, [])

  const handleMouseLeave = useCallback(() => {
    const map = mapRef.current?.getMap()
    if (map) map.getCanvas().style.cursor = ''
  }, [])

  // ── Popup content ─────────────────────────────────────────
  const renderPopup = () => {
    if (!popupInfo) return null
    const { location, lng, lat } = popupInfo
    const totalUpvotes = location.posts.reduce((s, p) => s + p.upvotes, 0)
    const allComments = location.posts.flatMap((p) => p.comments)
    const totalComments = allComments.length
    const topComments = [...allComments]
      .sort((a, b) => b.score - a.score)
      .slice(0, 20)
    const topPost = location.posts[0]

    return (
      <Popup
        longitude={lng}
        latitude={lat}
        anchor="bottom"
        offset={14}
        onClose={() => setPopupInfo(null)}
        closeOnClick={false}
        maxWidth="340px"
      >
        <div className="popup-inner">
          {/* Header */}
          <div className="popup-header">
            <div className="popup-title-row">
              <h2 className="popup-city">{location.city}</h2>
              <span className="popup-upvotes">▲ {totalUpvotes.toLocaleString()}</span>
            </div>
            <div className="popup-meta-row">
              <span className="popup-country">{location.country}</span>
              <span className="popup-subreddit">r/howislivingthere</span>
            </div>
          </div>

          <div className="popup-divider" />

          {/* Comments */}
          <div className="popup-comments-section">
            <div className="popup-comments-header">
              <p className="popup-comments-label">Top Comments</p>
              <span className="popup-comments-count">
                showing {topComments.length} of {totalComments}
              </span>
            </div>
            <div className="popup-comments-list">
              {topComments.map((comment, i) => (
                <CommentCard key={comment.redditId} comment={comment} isFirst={i === 0} />
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="popup-footer">
            <a
              href={topPost?.url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="popup-reddit-link"
            >
              View on Reddit →
            </a>
          </div>
        </div>
      </Popup>
    )
  }

  return (
    <div className="map-wrapper">
      <Map
        ref={mapRef}
        {...viewState}
        onMove={(e) => setViewState(e.viewState)}
        onMouseDown={handleInteractionStart}
        onTouchStart={handleInteractionStart}
        onMouseUp={handleInteractionEnd}
        onTouchEnd={handleInteractionEnd}
        onDragStart={handleInteractionStart}
        onDragEnd={handleInteractionEnd}
        onZoomStart={handleInteractionStart}
        onZoomEnd={handleInteractionEnd}
        onClick={handleClick}
        onLoad={() => setMapLoaded(true)}
        mapStyle={theme === 'dark' ? 'mapbox://styles/mapbox/dark-v11' : 'mapbox://styles/mapbox/light-v11'}
        mapboxAccessToken={MAPBOX_TOKEN}
        projection="globe"
        fog={theme === 'dark' ? FOG_DARK : FOG_LIGHT}
        style={{ width: '100%', height: '100%' }}
        interactiveLayerIds={['clusters', 'unclustered-point']}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        attributionControl={true}
      >
        <NavigationControl position="bottom-right" showCompass={false} />

        <Source
          id="locations"
          type="geojson"
          data={geojson}
          cluster={true}
          clusterMaxZoom={8}
          clusterRadius={50}
        >
          <Layer {...clusterLayer} />
          <Layer {...clusterCountLayer} />
          <Layer {...unclusteredPointLayer} />
        </Source>

        {renderPopup()}
      </Map>

      <HintBar mapInteracted={mapInteracted} />
    </div>
  )
}
