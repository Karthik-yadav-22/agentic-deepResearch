import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment! Please set it in your .env file.")

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

from coordinator import ResearchCoordinator

console = Console()


async def main() -> None:
    console.print(Panel.fit(
        "[bold cyan]Wissen E-Learn[/bold cyan]\n"
        "[dim]Learning platform powered by agentic deep research workflows[/dim]",
        border_style="cyan"
    ))

    # Get User Query
    query = Prompt.ask("\n[bold yellow]Enter the topic you want to research[/bold yellow]")

    if not query.strip():
        console.print("[bold red]⚠ Please enter a valid topic.[/bold red]")
        return

    console.print(f"\n[bold green]Starting deep research on:[/bold green] [italic]{query}[/italic]\n")

    # Run Research Coordinator
    coordinator = ResearchCoordinator(query)

    try:
        # Step 1: Generate search queries via query_agent
        console.rule("[bold cyan]Step 1: Query Analysis[/bold cyan]")
        query_result = await coordinator.generate_quries()

        # Step 2: Search + analyse each result via search_agent
        console.rule("[bold cyan]Step 2: Web Research[/bold cyan]")
        await coordinator.perform_research_for_queries(query_result.queries)

        # Step 3: Check if follow-up research is needed via follow_up_decision_agent
        console.rule("[bold cyan]Step 3: Follow-up Evaluation[/bold cyan]")
        follow_up = await coordinator.generate_followup()

        # Step 4 (optional): If follow-up needed, run another round of research
        if follow_up.should_follow_up and follow_up.queries:
            console.rule("[bold yellow]Step 4: Follow-up Research Round[/bold yellow]")
            await coordinator.perform_research_for_queries(follow_up.queries)
        else:
            console.print("[bold green]✓ No additional research needed.[/bold green]")

        # Step 5: Synthesise final report via synthesis_agent
        console.rule("[bold cyan]Step 5: Synthesising Final Report[/bold cyan]")
        report = await coordinator.synthesis_report()

        #Displaying Final Report
        console.print("\n")
        console.print(Panel(
            Markdown(report),
            title="[bold cyan]📄 Research Report[/bold cyan]",
            border_style="green",
            padding=(1, 2)
        ))

        # Optionally save report to file
        save = Prompt.ask(
            "\n[bold]Save report to a file?[/bold]",
            choices=["yes", "no"],
            default="no"
        )
        if save == "yes":
            filename = f"research_report_{query[:40].replace(' ', '_')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# Research Report: {query}\n\n")
                f.write(report)
            console.print(f"[bold green]Report saved to:[/bold green] {filename}")

    except KeyboardInterrupt:
        console.print("\n[bold red]Research interrupted by user.[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]An error occurred:[/bold red] {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())


#US East (N. Virginia) us-east-1