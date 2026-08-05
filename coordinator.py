import time
from agents import trace, Runner
from research_agents.query_agent import QueryPattern, query_agent
from research_agents.search_agent import search_agent
from research_agents.synthasis_agent import synthesis_agent
from research_agents.follow_up_agent import FollowUpDecisionResponse,follow_up_decision_agent
from research_agents.db_search_agent import search_db_for_topic
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from ddgs import DDGS
from pydantic import BaseModel

console=Console()

class SearchResult(BaseModel):
    title: str
    url: str
    summary: str 

class ResearchCoordinator:
    def __init__(self, query:str):
        self.query=query
        self.search_results = []
    
    async def research(self)->str:
        with trace("deep research workflow"):
            query_response = await self.generate_quries()
            await self.perform_research_for_queries(query_response.queries)

            follow_up = await self.generate_followup()
            if follow_up.should_follow_up and follow_up.queries:
                await self.perform_research_for_queries(follow_up.queries)

            report = await self.synthesis_report()
            return report
            
    async def generate_quries(self)->QueryPattern:
        with console.status("[bold cyan]Analysing...[/bold cyan]"):

            result = await Runner.run(query_agent, input=self.query)

            console.print("[yellow]Thoughts:[/yellow]",result.final_output.thinking_process)
            console.print(Panel(f"[bold cyan]Analysis:[/bold cyan]"))
            console.print("[bold yellow]Generated search queries:[/bold yellow]")
            for i,query in enumerate(result.final_output.queries,1):
                console.print(f"{i}:{query}")

            return result.final_output
        
    def duckduckgo_search(self, query:str):
        try:
            result=DDGS().text(query, region="ind-en", safesearch="on", max_results="1")
            return result
        except Exception as ex:
            return []

    async def search_results(self, quries: list[str]):
        all_search_results={}
        for query in quries:
            search=self.duckduckgo_search(query)
            all_search_results[query]=search
            
    async def perform_research_for_queries(self, queries: list[str]):
        for query in queries:
            console.print(f"\n[bold cyan]Searching web & books:[/bold cyan] {query}")
            web_results = self.duckduckgo_search(query)
            for result in web_results:
                start = time.time()
                input_text = f"Title: {result['title']}\nURL: {result['href']}"
                summary = await Runner.run(search_agent, input_text)
                elapsed = round(time.time() - start, 2)
                self.search_results.append(SearchResult(
                    title=result["title"],
                    url=result["href"],
                    summary=summary.final_output
                ))
                console.print(f"  [green]Web:[/green] {result['title']} ({elapsed}s)")

            book_results = await search_db_for_topic(query)
            for result in book_results:
                self.search_results.append(SearchResult(
                    title=result["title"],
                    url=result["url"],
                    summary=result["summary"]
                ))
                console.print(f"  [magenta]Book:[/magenta] {result['title']}")

    async def synthesis_report(self) -> str:
         with console.status("[bold cyan]Synthesizing research findings...[/bold cyan]") as status:
            findings_text = f"Query: {self.query}\n\nSearch Results:\n"
            for i, result in enumerate(self.search_results, 1):
                findings_text += f"\n{i}. Title: {result.title}\n   URL: {result.url}\n   Summary: {result.summary}\n"

            result = await Runner.run(synthesis_agent, input=findings_text)

            return result.final_output
         
    async def generate_followup(self) -> FollowUpDecisionResponse:
        with console.status("[bold cyan]Evaluating if more research is needed...[/bold cyan]") as status:
            findings_text = f"Original Query: {self.query}\n\nCurrent Findings:\n"
            for i, result in enumerate(self.search_results, 1):
                findings_text += f"\n{i}. Title: {result.title}\n   URL: {result.url}\n   Summary: {result.summary}\n"

            result = await Runner.run(follow_up_decision_agent, input=findings_text)

            console.print(Panel(f"[bold cyan]Follow-up Decision[/bold cyan]"))
            console.print(f"[yellow]Decision:[/yellow] {'More research needed' if result.final_output.should_follow_up else 'Research complete'}")
            console.print(f"[yellow]Reasoning:[/yellow] {result.final_output.reasoning}")

            if result.final_output.should_follow_up:
                console.print("\n[yellow]Follow-up Queries:[/yellow]")
                for i, query in enumerate(result.final_output.queries, 1):
                    console.print(f"  {i}. {query}")

            return result.final_output
