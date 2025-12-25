#!/usr/bin/env python3
"""
Test the process_claim_document tool with Azure Content Understanding.
"""
import os
import sys
import logging

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from app.core.logging_config import configure_logging
configure_logging()

logger = logging.getLogger(__name__)
console = Console()


def test_tool_availability():
    """Test that the tool is properly registered."""
    from app.workflow.tools import process_claim_document, ALL_TOOLS, TOOLS_BY_NAME
    
    console.print("\n[bold cyan]Testing Tool Registration[/bold cyan]")
    
    # Check tool is in ALL_TOOLS
    tool_names = [t.name for t in ALL_TOOLS]
    assert "process_claim_document" in tool_names, "Tool not in ALL_TOOLS"
    console.print("✅ process_claim_document in ALL_TOOLS")
    
    # Check tool is in TOOLS_BY_NAME
    assert "process_claim_document" in TOOLS_BY_NAME, "Tool not in TOOLS_BY_NAME"
    console.print("✅ process_claim_document in TOOLS_BY_NAME")
    
    # Check tool has correct metadata
    tool = TOOLS_BY_NAME["process_claim_document"]
    assert tool.name == "process_claim_document"
    assert "Content Understanding" in tool.description
    console.print("✅ Tool has correct name and description")
    
    return True


def test_service_availability():
    """Test that Content Understanding service is available."""
    from app.services.content_understanding_service import get_content_understanding_service
    
    console.print("\n[bold cyan]Testing Content Understanding Service[/bold cyan]")
    
    service = get_content_understanding_service()
    is_available = service.is_available()
    
    if is_available:
        console.print("✅ Content Understanding service is available")
    else:
        console.print("[yellow]⚠️ Content Understanding service not configured[/yellow]")
        console.print("[dim]Set AZURE_CONTENT_UNDERSTANDING_ENDPOINT, KEY, and ANALYZER_ID[/dim]")
    
    return is_available


def test_file_not_found():
    """Test error handling for missing file."""
    from app.workflow.tools import process_claim_document
    
    console.print("\n[bold cyan]Testing Error Handling - File Not Found[/bold cyan]")
    
    result = process_claim_document.invoke({"file_path": "/nonexistent/file.pdf"})
    
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()
    console.print("✅ Correctly handles missing file")
    
    return True


def test_with_sample_document(sample_path: str = None):
    """Test with an actual document if available."""
    from app.workflow.tools import process_claim_document
    
    console.print("\n[bold cyan]Testing With Sample Document[/bold cyan]")
    
    # Try to find a sample document
    if sample_path and os.path.exists(sample_path):
        test_file = sample_path
    else:
        # Check common locations for test documents
        possible_paths = [
            "tests/fixtures/sample_claim.pdf",
            "tests/data/sample_claim.pdf",
            "../frontend/public/sample_claim.pdf",
        ]
        test_file = None
        for path in possible_paths:
            if os.path.exists(path):
                test_file = path
                break
    
    if not test_file:
        console.print("[yellow]⚠️ No sample document found - skipping document test[/yellow]")
        console.print("[dim]Provide a path argument or add a sample PDF to tests/fixtures/[/dim]")
        return None
    
    console.print(f"📄 Testing with: {test_file}")
    
    result = process_claim_document.invoke({"file_path": test_file})
    
    if result["status"] == "success":
        console.print(f"✅ Document processed successfully")
        console.print(f"   Fields extracted: {result['field_count']}")
        console.print(f"   Tables found: {result['table_count']}")
        
        # Display extracted fields
        if result["extracted_fields"]:
            table = Table(title="Extracted Fields")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Confidence", style="yellow")
            
            for field, value in result["extracted_fields"].items():
                confidence = result["confidence_scores"].get(field, "N/A")
                if isinstance(confidence, float):
                    confidence = f"{confidence:.2%}"
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 50:
                    str_value = str_value[:47] + "..."
                table.add_row(field, str_value, str(confidence))
            
            console.print(table)
        
        return True
    else:
        console.print(f"[red]❌ Error: {result.get('message', 'Unknown error')}[/red]")
        return False


def main():
    """Run all tests."""
    console.print(Panel.fit(
        "[bold blue]Process Claim Document Tool Tests[/bold blue]\n"
        "[dim]Testing Azure Content Understanding integration[/dim]",
        border_style="blue"
    ))
    
    results = {}
    
    # Test 1: Tool availability
    try:
        results["tool_registration"] = test_tool_availability()
    except Exception as e:
        console.print(f"[red]❌ Tool registration test failed: {e}[/red]")
        results["tool_registration"] = False
    
    # Test 2: Service availability
    try:
        results["service_available"] = test_service_availability()
    except Exception as e:
        console.print(f"[red]❌ Service availability test failed: {e}[/red]")
        results["service_available"] = False
    
    # Test 3: Error handling
    try:
        results["error_handling"] = test_file_not_found()
    except Exception as e:
        console.print(f"[red]❌ Error handling test failed: {e}[/red]")
        results["error_handling"] = False
    
    # Test 4: Document processing (optional)
    sample_path = sys.argv[1] if len(sys.argv) > 1 else None
    if results.get("service_available"):
        try:
            results["document_processing"] = test_with_sample_document(sample_path)
        except Exception as e:
            console.print(f"[red]❌ Document processing test failed: {e}[/red]")
            results["document_processing"] = False
    else:
        results["document_processing"] = None
    
    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Test Summary[/bold]")
    console.print("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test_name, result in results.items():
        if result is True:
            status = "[green]✅ PASSED[/green]"
        elif result is False:
            status = "[red]❌ FAILED[/red]"
        else:
            status = "[yellow]⏭️ SKIPPED[/yellow]"
        console.print(f"  {test_name}: {status}")
    
    console.print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
