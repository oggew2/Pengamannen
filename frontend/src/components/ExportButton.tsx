import styles from '../styles/App.module.css';

interface Props {
  url: string;
  label?: string;
}

export function ExportButton({ url, label = 'Export CSV' }: Props) {
  const baseUrl = import.meta.env.DEV ? '/api' : '/api';
  
  return (
    <a 
      href={`${baseUrl}${url}`} 
      download 
      className={styles.btnSmall}
      style={{ textDecoration: 'none', display: 'inline-block' }}
    >
      📥 {label}
    </a>
  );
}
