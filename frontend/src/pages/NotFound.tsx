import { Link } from 'react-router-dom';
import styles from '../styles/App.module.css';

export function NotFound() {
  return (
    <div className={styles.notFound}>
      <div className={styles.notFoundCode}>404</div>
      <p>Page not found</p>
      <Link to="/" className={styles.cardLink}>← Back to Dashboard</Link>
    </div>
  );
}
