#!/usr/bin/env python3
"""
Automated Test Runner for Börslabbet App Test Suite.

Runs comprehensive tests with proper organization and reporting.
"""
import subprocess
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


class TestRunner:
    """Automated test runner with comprehensive reporting."""
    
    def __init__(self, backend_path: str = "/Users/ewreosk/Kiro/borslabbet-app/backend"):
        self.backend_path = Path(backend_path)
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def setup_environment(self) -> bool:
        """Set up test environment and dependencies."""
        print("🔧 Setting up test environment...")
        
        try:
            # Change to backend directory
            os.chdir(self.backend_path)
            
            # Install test dependencies
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Failed to install dependencies: {result.stderr}")
                return False
            
            # Create necessary directories
            (self.backend_path / "reports").mkdir(exist_ok=True)
            (self.backend_path / "htmlcov").mkdir(exist_ok=True)
            
            print("✅ Test environment setup complete")
            return True
            
        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            return False
    
    def run_test_suite(self, test_type: str, test_path: str, markers: List[str] = None) -> Dict[str, Any]:
        """Run a specific test suite and return results."""
        print(f"\n🧪 Running {test_type} tests...")
        
        # Build pytest command
        cmd = [sys.executable, "-m", "pytest", test_path, "-v"]
        
        # Add markers if specified
        if markers:
            for marker in markers:
                cmd.extend(["-m", marker])
        
        # Add coverage and reporting options
        cmd.extend([
            "--tb=short",
            "--cov=.",
            "--cov-report=term-missing",
            f"--html=reports/{test_type}_report.html",
            "--self-contained-html"
        ])
        
        start_time = time.time()
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
            end_time = time.time()
            
            # Parse results
            test_result = {
                "test_type": test_type,
                "duration": end_time - start_time,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "timestamp": datetime.now().isoformat()
            }
            
            # Extract test statistics from output
            test_result.update(self._parse_pytest_output(result.stdout))
            
            return test_result
            
        except subprocess.TimeoutExpired:
            return {
                "test_type": test_type,
                "duration": 1800,
                "return_code": -1,
                "success": False,
                "error": "Test suite timed out after 30 minutes",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "test_type": test_type,
                "duration": 0,
                "return_code": -1,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse pytest output to extract test statistics."""
        stats = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "warnings": 0
        }
        
        lines = output.split('\n')
        
        for line in lines:
            # Look for summary line like "= 25 passed, 2 failed, 1 skipped in 45.67s ="
            if " passed" in line and " in " in line and "=" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i + 1 < len(parts):
                        count = int(part)
                        status = parts[i + 1]
                        
                        if "passed" in status:
                            stats["passed"] = count
                        elif "failed" in status:
                            stats["failed"] = count
                        elif "skipped" in status:
                            stats["skipped"] = count
                        elif "error" in status:
                            stats["errors"] = count
                
                stats["total_tests"] = stats["passed"] + stats["failed"] + stats["skipped"] + stats["errors"]
                break
        
        return stats
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites in order."""
        self.start_time = time.time()
        
        print("🚀 Starting Börslabbet App Test Suite")
        print("=" * 60)
        
        # Test suites to run
        test_suites = [
            {
                "name": "unit",
                "path": "tests/unit/",
                "markers": ["unit"],
                "description": "Unit Tests - Strategy calculations and core logic"
            },
            {
                "name": "integration_api",
                "path": "tests/integration/test_api_endpoints.py",
                "markers": ["api", "integration"],
                "description": "API Integration Tests - All endpoints and validations"
            },
            {
                "name": "integration_avanza",
                "path": "tests/integration/test_avanza_integration.py", 
                "markers": ["integration"],
                "description": "Avanza Integration Tests - Data quality and resilience"
            },
            {
                "name": "performance",
                "path": "tests/integration/test_performance_reliability.py",
                "markers": ["performance"],
                "description": "Performance Tests - Load times and cache efficiency"
            },
            {
                "name": "e2e",
                "path": "tests/e2e/",
                "markers": ["e2e"],
                "description": "End-to-End Tests - Complete user journeys"
            }
        ]
        
        # Run each test suite
        for suite in test_suites:
            print(f"\n📋 {suite['description']}")
            print("-" * 50)
            
            result = self.run_test_suite(
                suite["name"],
                suite["path"],
                suite.get("markers")
            )
            
            self.test_results[suite["name"]] = result
            
            # Print immediate results
            if result["success"]:
                print(f"✅ {suite['name']} tests PASSED ({result.get('passed', 0)} tests, {result['duration']:.1f}s)")
            else:
                print(f"❌ {suite['name']} tests FAILED ({result.get('failed', 0)} failures, {result['duration']:.1f}s)")
                if result.get("error"):
                    print(f"   Error: {result['error']}")
        
        self.end_time = time.time()
        
        # Generate comprehensive report
        return self._generate_final_report()
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_duration = self.end_time - self.start_time
        
        # Aggregate statistics
        total_stats = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "suites_passed": 0,
            "suites_failed": 0
        }
        
        for suite_name, result in self.test_results.items():
            if result["success"]:
                total_stats["suites_passed"] += 1
            else:
                total_stats["suites_failed"] += 1
            
            for key in ["total_tests", "passed", "failed", "skipped", "errors"]:
                total_stats[key] += result.get(key, 0)
        
        # Calculate success rates
        success_rate = (total_stats["passed"] / total_stats["total_tests"] * 100) if total_stats["total_tests"] > 0 else 0
        suite_success_rate = (total_stats["suites_passed"] / len(self.test_results) * 100) if self.test_results else 0
        
        final_report = {
            "summary": {
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
                "total_duration": total_duration,
                "success_rate": success_rate,
                "suite_success_rate": suite_success_rate,
                **total_stats
            },
            "suite_results": self.test_results,
            "go_no_go_assessment": self._assess_go_no_go()
        }
        
        # Save report to file
        report_file = self.backend_path / "reports" / "comprehensive_test_report.json"
        with open(report_file, 'w') as f:
            json.dump(final_report, f, indent=2)
        
        return final_report
    
    def _assess_go_no_go(self) -> Dict[str, Any]:
        """Assess go/no-go status based on test results."""
        assessment = {
            "overall_status": "GO",
            "critical_failures": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Critical must-pass items
        critical_checks = {
            "unit_tests_pass": self.test_results.get("unit", {}).get("success", False),
            "api_tests_pass": self.test_results.get("integration_api", {}).get("success", False),
            "performance_acceptable": self.test_results.get("performance", {}).get("success", False),
            "no_critical_failures": all(
                result.get("failed", 0) == 0 
                for result in self.test_results.values()
            )
        }
        
        # Check critical items
        for check, passed in critical_checks.items():
            if not passed:
                assessment["critical_failures"].append(check)
                assessment["overall_status"] = "NO-GO"
        
        # Performance gates
        performance_result = self.test_results.get("performance", {})
        if performance_result.get("duration", 0) > 300:  # 5 minutes
            assessment["warnings"].append("Performance tests took longer than expected")
        
        # Coverage and quality gates
        total_passed = sum(result.get("passed", 0) for result in self.test_results.values())
        total_tests = sum(result.get("total_tests", 0) for result in self.test_results.values())
        
        if total_tests > 0:
            pass_rate = total_passed / total_tests
            if pass_rate < 0.95:  # 95% pass rate required
                assessment["critical_failures"].append(f"Pass rate {pass_rate:.1%} below 95% threshold")
                assessment["overall_status"] = "NO-GO"
        
        # Generate recommendations
        if assessment["overall_status"] == "GO":
            assessment["recommendations"].append("All critical tests passed - ready for deployment")
        else:
            assessment["recommendations"].append("Address critical failures before deployment")
            assessment["recommendations"].extend([
                f"Fix: {failure}" for failure in assessment["critical_failures"]
            ])
        
        return assessment
    
    def print_final_summary(self, report: Dict[str, Any]):
        """Print comprehensive test summary."""
        print("\n" + "=" * 80)
        print("🎯 BÖRSLABBET APP TEST SUITE - FINAL REPORT")
        print("=" * 80)
        
        summary = report["summary"]
        
        print(f"⏱️  Total Duration: {summary['total_duration']:.1f} seconds")
        print(f"📊 Test Statistics:")
        print(f"   • Total Tests: {summary['total_tests']}")
        print(f"   • Passed: {summary['passed']} ({summary['success_rate']:.1f}%)")
        print(f"   • Failed: {summary['failed']}")
        print(f"   • Skipped: {summary['skipped']}")
        print(f"   • Errors: {summary['errors']}")
        
        print(f"\n📋 Test Suites:")
        print(f"   • Passed: {summary['suites_passed']}/{len(self.test_results)} ({summary['suite_success_rate']:.1f}%)")
        print(f"   • Failed: {summary['suites_failed']}")
        
        # Go/No-Go Assessment
        assessment = report["go_no_go_assessment"]
        status_emoji = "✅" if assessment["overall_status"] == "GO" else "❌"
        
        print(f"\n{status_emoji} GO/NO-GO ASSESSMENT: {assessment['overall_status']}")
        
        if assessment["critical_failures"]:
            print("❌ Critical Failures:")
            for failure in assessment["critical_failures"]:
                print(f"   • {failure}")
        
        if assessment["warnings"]:
            print("⚠️  Warnings:")
            for warning in assessment["warnings"]:
                print(f"   • {warning}")
        
        print("\n💡 Recommendations:")
        for rec in assessment["recommendations"]:
            print(f"   • {rec}")
        
        print(f"\n📁 Detailed reports available in: {self.backend_path}/reports/")
        print("=" * 80)


def main():
    """Main test runner entry point."""
    runner = TestRunner()
    
    # Setup environment
    if not runner.setup_environment():
        sys.exit(1)
    
    # Run all tests
    try:
        report = runner.run_all_tests()
        runner.print_final_summary(report)
        
        # Exit with appropriate code
        if report["go_no_go_assessment"]["overall_status"] == "GO":
            print("\n🎉 All tests passed! Ready for deployment.")
            sys.exit(0)
        else:
            print("\n🚫 Critical tests failed. Deployment blocked.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
