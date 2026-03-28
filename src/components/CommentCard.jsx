import './CommentCard.css'

function CommentCard({ comment, isFirst }) {
  return (
    <div className={`comment-card ${isFirst ? 'comment-card--first' : ''}`}>
      <p className="comment-text">"{comment.text}"</p>
      <div className="comment-meta">
        <span className="comment-author">u/{comment.author}</span>
        <span className="comment-score">▲ {comment.score.toLocaleString()}</span>
      </div>
    </div>
  )
}

export default CommentCard
