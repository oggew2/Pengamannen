import { NavLink } from 'react-router-dom';
import styles from '../styles/App.module.css';

export function Navigation() {
  return (
    <nav className={styles.nav}>
      <div className={`${styles.container} ${styles.navInner}`}>
        <NavLink to="/" className={styles.logo}>Börslabbet</NavLink>
        <ul className={styles.navLinks}>
          <li><NavLink to="/" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Dashboard</NavLink></li>
          <li><NavLink to="/strategies/momentum" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Momentum</NavLink></li>
          <li><NavLink to="/strategies/value" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Värde</NavLink></li>
          <li><NavLink to="/strategies/dividend" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Utdelning</NavLink></li>
          <li><NavLink to="/strategies/quality" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Kvalitet</NavLink></li>
          <li><NavLink to="/portfolio/sverige" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Portfölj</NavLink></li>
          <li><NavLink to="/portfolio/combiner" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Kombinator</NavLink></li>
          <li><NavLink to="/backtesting" className={({isActive}) => isActive ? styles.navLinkActive : styles.navLink}>Backtest</NavLink></li>
        </ul>
      </div>
    </nav>
  );
}
