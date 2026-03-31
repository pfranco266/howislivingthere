import CommentCard from './CommentCard'
import './BottomSheet.css'

function BottomSheet({ locationInfo, onClose }) {
  if (!locationInfo) return null

  const { location } = locationInfo
  const totalUpvotes = location.posts.reduce((s, p) => s + p.upvotes, 0)
  const allComments = location.posts.flatMap((p) => p.comments)
  const topComments = [...allComments].sort((a, b) => b.score - a.score).slice(0, 20)
  const topPost = location.posts[0]

  return (
    <div className="bottom-sheet-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label={`Living in ${location.city}`}>
      <div className="bottom-sheet" onClick={(e) => e.stopPropagation()}>
        {/* Drag handle */}
        <div className="bottom-sheet-handle" aria-hidden="true" />

        {/* Close button */}
        <button className="bottom-sheet-close" onClick={onClose} aria-label="Close">
          ✕
        </button>

        {/* Header */}
        <div className="bottom-sheet-header">
          <div className="bottom-sheet-title-row">
            <h2 className="bottom-sheet-city">{location.city}</h2>
            <span className="bottom-sheet-upvotes">▲ {totalUpvotes.toLocaleString()}</span>
          </div>
          <div className="bottom-sheet-meta-row">
            <span className="bottom-sheet-country">{location.country}</span>
            <span className="bottom-sheet-subreddit">r/howislivingthere</span>
          </div>
        </div>

        <div className="bottom-sheet-divider" />

        {/* Comments */}
        <div className="bottom-sheet-comments-header">
          <p className="bottom-sheet-comments-label">Top Comments</p>
          <span className="bottom-sheet-comments-count">
            showing {topComments.length} of {allComments.length}
          </span>
        </div>

        <div className="bottom-sheet-scroll">
          <div className="bottom-sheet-comments-list">
            {topComments.map((comment, i) => (
              <CommentCard key={comment.redditId} comment={comment} isFirst={i === 0} />
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="bottom-sheet-footer">
          <a
            href={topPost?.url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="bottom-sheet-reddit-link"
          >
            View on Reddit →
          </a>
        </div>
      </div>
    </div>
  )
}

export default BottomSheet
