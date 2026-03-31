import { useState } from 'react'
import './CommentCard.css'

const TRUNCATE_LENGTH = 200

function CommentCard({ comment, isFirst }) {
  const isLong = comment.text.length > TRUNCATE_LENGTH
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`comment-card ${isFirst ? 'comment-card--first' : ''}`}>
      <div className={`comment-text-wrap ${isLong && !expanded ? 'comment-text-wrap--collapsed' : ''}`}>
        <p className="comment-text">
          &ldquo;{expanded || !isLong ? comment.text : comment.text.slice(0, TRUNCATE_LENGTH).trimEnd() + '\u2026'}&rdquo;
        </p>
        {isLong && !expanded && <div className="comment-fade" aria-hidden="true" />}
      </div>

      {isLong && (
        <button
          className="comment-expand-btn"
          onClick={() => setExpanded(e => !e)}
          aria-label={expanded ? 'Show less of this comment' : 'Read full comment'}
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}

      <div className="comment-meta">
        <span className="comment-author">u/{comment.author}</span>
        <span className="comment-score">▲ {comment.score.toLocaleString()}</span>
      </div>
    </div>
  )
}

export default CommentCard
