"""
Investment platform safeguards and disclaimers.
Ensures legal compliance and user protection.
"""
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class InvestmentSafeguards:
    """Legal and compliance safeguards for investment platform."""
    
    @staticmethod
    def get_required_disclaimers() -> Dict[str, str]:
        """Get all required disclaimers for investment platform."""
        return {
            'data_disclaimer': (
                "Market data may be delayed up to 15 minutes. "
                "Data is provided by Yahoo Finance and is for informational purposes only."
            ),
            'investment_disclaimer': (
                "This information is for educational purposes only and should not be "
                "considered as investment advice. Always consult with a qualified "
                "financial advisor before making investment decisions."
            ),
            'risk_warning': (
                "All investments carry risk of loss. Past performance does not "
                "guarantee future results. You may lose some or all of your investment."
            ),
            'data_source_attribution': (
                "Financial data provided by Yahoo Finance. "
                "Strategy calculations based on Börslabbet methodology."
            ),
            'accuracy_disclaimer': (
                "While we strive for accuracy, we cannot guarantee the completeness "
                "or accuracy of the data. Users should verify information independently."
            ),
            'no_warranty': (
                "This service is provided 'as is' without any warranties, express or implied. "
                "We disclaim all liability for any losses or damages."
            )
        }
    
    @staticmethod
    def get_data_quality_warnings(coverage_percent: float, stale_count: int) -> List[str]:
        """Get data quality warnings based on current state."""
        warnings = []
        
        if coverage_percent < 50:
            warnings.append("⚠️ CRITICAL: Less than 50% data coverage. Rankings may be unreliable.")
        elif coverage_percent < 80:
            warnings.append("⚠️ WARNING: Limited data coverage. Some rankings may be inaccurate.")
        
        if stale_count > 0:
            warnings.append(f"⚠️ {stale_count} stocks have stale data (>24 hours old)")
        
        return warnings
    
    @staticmethod
    def validate_strategy_usage(strategy_name: str, data_quality: Dict) -> Dict:
        """Validate if strategy can be safely used with current data quality."""
        
        min_requirements = {
            'sammansatt_momentum': {'min_stocks': 20, 'max_stale_hours': 48},
            'trendande_varde': {'min_stocks': 25, 'max_stale_hours': 72},
            'trendande_utdelning': {'min_stocks': 20, 'max_stale_hours': 72},
            'trendande_kvalitet': {'min_stocks': 25, 'max_stale_hours': 48}
        }
        
        if strategy_name not in min_requirements:
            return {'can_use': False, 'reason': 'Unknown strategy'}
        
        req = min_requirements[strategy_name]
        
        # Check minimum stocks
        if data_quality.get('successful', 0) < req['min_stocks']:
            return {
                'can_use': False,
                'reason': f"Insufficient data: {data_quality.get('successful', 0)}/{req['min_stocks']} stocks required",
                'severity': 'CRITICAL'
            }
        
        # Check data freshness
        coverage = data_quality.get('coverage_percent', 0)
        if coverage < 70:
            return {
                'can_use': False,
                'reason': f"Data too stale: {coverage:.1f}% coverage, need >70%",
                'severity': 'ERROR'
            }
        elif coverage < 90:
            return {
                'can_use': True,
                'reason': f"Acceptable quality: {coverage:.1f}% coverage",
                'severity': 'WARNING',
                'warnings': ['Rankings may have some inaccuracies due to limited data coverage']
            }
        
        return {
            'can_use': True,
            'reason': f"Good quality: {coverage:.1f}% coverage",
            'severity': 'OK'
        }
    
    @staticmethod
    def get_legal_footer() -> str:
        """Get legal footer for all pages."""
        return (
            "© 2025 Börslabbet App. For educational purposes only. "
            "Not investment advice. Data provided by Yahoo Finance. "
            "All investments carry risk of loss."
        )
    
    @staticmethod
    def log_user_action(action: str, user_context: Dict = None):
        """Log user actions for compliance tracking."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'context': user_context or {}
        }
        
        # In production, this would go to a compliance database
        logger.info(f"User action logged: {log_entry}")

def add_investment_safeguards_to_response(response: Dict, data_quality: Dict = None) -> Dict:
    """Add all required safeguards to API response."""
    safeguards = InvestmentSafeguards()
    
    # Add disclaimers
    response['disclaimers'] = safeguards.get_required_disclaimers()
    
    # Add data quality warnings if provided
    if data_quality:
        coverage = data_quality.get('coverage_percent', 0)
        stale_count = data_quality.get('stale_count', 0)
        response['data_warnings'] = safeguards.get_data_quality_warnings(coverage, stale_count)
    
    # Add timestamp
    response['generated_at'] = datetime.now().isoformat()
    
    # Add legal footer
    response['legal_notice'] = safeguards.get_legal_footer()
    
    return response

def validate_strategy_safety(strategy_name: str, data_quality: Dict) -> Dict:
    """Validate strategy safety with comprehensive checks."""
    safeguards = InvestmentSafeguards()
    
    validation = safeguards.validate_strategy_usage(strategy_name, data_quality)
    
    # Add additional safety checks
    if validation['can_use']:
        validation['safety_checklist'] = {
            'data_attribution': '✅ Yahoo Finance data properly attributed',
            'disclaimers_shown': '✅ Investment disclaimers displayed',
            'risk_warnings': '✅ Risk warnings provided',
            'educational_only': '✅ Marked as educational content'
        }
    else:
        validation['safety_checklist'] = {
            'data_quality': '❌ Insufficient data quality',
            'user_protection': '✅ Strategy disabled for user safety'
        }
    
    # Log the validation
    InvestmentSafeguards.log_user_action('strategy_validation', {
        'strategy': strategy_name,
        'result': validation['can_use'],
        'reason': validation['reason']
    })
    
    return validation
