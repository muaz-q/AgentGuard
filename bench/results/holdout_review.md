# holdout set: findings for hand review

Seed 2026; up to 1000 per rule. Verdicts are recorded in labels.csv.

## AG001 khoj-ai/khoj src/khoj/routers/api_chat.py:1576

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/routers/api_chat.py#L1576

> call to `process_chat_request` inside `while` loop (line 1528) with no iteration cap

```python
 1552              if "q" not in data:
 1553                  await websocket.send_text(json.dumps({"error": "Missing required field 'q' in chat message"}))
 1554                  continue
 1555  
 1556              body = ChatRequestBody(**data)
 1557  
 1558              # Apply rate limiting manually
 1559              try:
 1560                  await rate_limiter_per_minute.check_websocket(websocket)
 1561                  await rate_limiter_per_day.check_websocket(websocket)
 1562                  image_rate_limiter.check_websocket(websocket, body)
 1563              except HTTPException as e:
 1564                  await websocket.send_text(json.dumps({"error": e.detail}))
 1565                  continue
 1566  
 1567              # Cancel any ongoing task before starting a new one
 1568              if current_task and not current_task.done():
 1569                  current_task.cancel()
 1570                  try:
 1571                      await current_task
 1572                  except asyncio.CancelledError:
 1573                      pass
 1574  
 1575              # Create a new task for processing the chat request
 1576>             current_task = asyncio.create_task(process_chat_request(websocket, body, common, interrupt_queue))
 1577  
 1578      except WebSocketDisconnect:
 1579          logger.info(f"WebSocket disconnected for user {websocket.scope['user'].object.id}")
 1580          if current_task and not current_task.done():
 1581              interrupt_queue.put_nowait(ChatEvent.INTERRUPT.value)
 1582      except Exception as e:
 1583          logger.error(f"Error in websocket chat: {e}", exc_info=True)
 1584          if current_task and not current_task.done():
```

## AG002 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/copilot/eval/style/generation.py:156

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/copilot/eval/style/generation.py#L156

> LLM call (openai.chat) re-sends a history that grows every iteration; input tokens grow quadratically

```python
  132      *,
  133      model: str,
  134      expert: Expert | None,
  135      roster: list[Expert],
  136      user_message: str,
  137  ) -> Turn:
  138      system: dict[str, Any] = {"role": "system", "content": chat_system_prompt(expert)}
  139      tools: list[dict[str, Any]] = [dict(t) for t in expert_tools(expert)]
  140      headers: dict[str, str] | None = None
  141      if _supports_prompt_cache_markers(model):
  142          system = _build_cached_system_message(system)
  143          tools = _mark_tools_with_cache_control(tools)
  144          headers = _fresh_anthropic_caching_headers()
  145      messages: list[dict[str, Any]] = [system, {"role": "user", "content": user_message}]
  146      extra_body = (
  147          {"usage": {"include": True}}
  148          if config.baseline_provider == "openrouter"
  149          else None
  150      )
  151      turn = Turn(
  152          text="", truncated=False, usage=Usage(model=model, cost_usd=0.0), tool_calls=[]
  153      )
  154      texts: list[str] = []
  155      for _ in range(MAX_TOOL_ROUNDS):
  156>         completion = await client.chat.completions.create(
  157              model=model,
  158              messages=cast(list[ChatCompletionMessageParam], messages),
  159              tools=cast(list[ChatCompletionToolParam], tools),
  160              max_tokens=GENERATION_MAX_TOKENS,
  161              timeout=GENERATION_TIMEOUT_SECONDS,
  162              extra_body=extra_body,
  163              extra_headers=headers,
  164          )
```

## AG002 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/blocks/llm.py:680

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/blocks/llm.py#L680

> call to `AIStructuredResponseGeneratorBlock.llm_call` re-sends a history that grows every iteration; input tokens grow quadratically

```python
  656              )
  657              prompt.append({"role": "system", "content": sys_prompt})
  658  
  659          if input_data.prompt:
  660              prompt.append({"role": "user", "content": input_data.prompt})
  661  
  662          def validate_response(parsed: object) -> str | None:
  663              try:
  664                  if not isinstance(parsed, dict):
  665                      return f"Expected a dictionary, but got {type(parsed)}"
  666                  miss_keys = set(input_data.expected_format.keys()) - set(parsed.keys())
  667                  if miss_keys:
  668                      return f"Missing keys: {miss_keys}"
  669                  return None
  670              except JSONDecodeError as e:
  671                  return f"JSON decode error: {e}"
  672  
  673          error_feedback_message = ""
  674          llm_model = input_data.model
  675          total_provider_cost: float | None = None
  676  
  677          for retry_count in range(input_data.retry):
  678              logger.debug(f"LLM request: {prompt}")
  679              try:
  680>                 llm_response = await self.llm_call(
  681                      credentials=credentials,
  682                      llm_model=llm_model,
  683                      prompt=prompt,
  684                      compress_prompt_to_fit=input_data.compress_prompt_to_fit,
  685                      force_json_output=(
  686                          input_data.force_json_output
  687                          and bool(input_data.expected_format)
  688                      ),
```

## AG002 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/executor/simulator.py:217

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/executor/simulator.py#L217

> LLM call (openai.chat) re-sends a history that grows every iteration; input tokens grow quadratically

```python
  193      # Local backends govern their own context window at launch (e.g.
  194      # OLLAMA_CONTEXT_LENGTH), so we send no per-request num_ctx hint —
  195      # Ollama's OpenAI shim ignores ``options.num_ctx`` anyway.
  196      from backend.copilot.sdk.env import config as chat_cfg
  197  
  198      if chat_cfg.transport.name == "local":
  199          extra_body: dict[str, Any] = {}
  200      else:
  201          # Shallow-copy the constant rather than sharing the reference — see
  202          # the matching pattern in ``baseline/service.py`` and
  203          # ``activity_status_generator.py``. Defends against intermediate
  204          # layers ever mutating ``extra_body`` and corrupting the shared
  205          # module-level dict for every future call.
  206          extra_body = dict(_OPENROUTER_INCLUDE_USAGE_COST)
  207  
  208      model = _simulator_model()
  209      last_error: Exception | None = None
  210      last_parsed: dict[str, Any] | None = None
  211      messages: list[ChatCompletionMessageParam] = [
  212          {"role": "system", "content": system_prompt},
  213          {"role": "user", "content": user_prompt},
  214      ]
  215      for attempt in range(_MAX_JSON_RETRIES):
  216          try:
  217>             response = await client.chat.completions.create(
  218                  model=model,
  219                  temperature=_TEMPERATURE,
  220                  response_format={"type": "json_object"},
  221                  messages=messages,
  222                  extra_body=extra_body,
  223              )
  224              if not response.choices:
  225                  raise ValueError("LLM returned empty choices array")
```

## AG002 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/blocks/orchestrator.py:2168

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/blocks/orchestrator.py#L2168

> call to `OrchestratorBlock._attempt_llm_call_with_validation` re-sends a history that grows every iteration; input tokens grow quadratically

```python
 2144                  input_data=input_data,
 2145                  credentials=credentials,
 2146                  tool_functions=tool_functions,
 2147                  prompt=prompt,
 2148                  graph_exec_id=graph_exec_id,
 2149                  node_id=node_id,
 2150                  node_exec_id=node_exec_id,
 2151                  user_id=user_id,
 2152                  graph_id=graph_id,
 2153                  graph_version=graph_version,
 2154                  execution_context=execution_context,
 2155                  execution_processor=execution_processor,
 2156              ):
 2157                  yield result
 2158              return
 2159  
 2160          # One-off mode: single LLM call and yield tool calls for external execution
 2161          current_prompt = list(prompt)
 2162          max_attempts = max(1, int(input_data.retry))
 2163          response = None
 2164  
 2165          last_error = None
 2166          for _ in range(max_attempts):
 2167              try:
 2168>                 response = await self._attempt_llm_call_with_validation(
 2169                      credentials,
 2170                      input_data,
 2171                      current_prompt,
 2172                      tool_functions,
 2173                      execution_context,
 2174                  )
 2175                  break
 2176  
```

## AG002 khoj-ai/khoj src/khoj/routers/research.py:539

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/routers/research.py#L539

> call to `apick_next_tool` re-sends a history that grows every iteration; input tokens grow quadratically

```python
  515              break
  516  
  517          # Update the query for the current research iteration
  518          if interrupt_query := get_message_from_queue(interrupt_queue):
  519              if interrupt_query == abort_message:
  520                  cancellation_event.set()
  521                  logger.debug(f"Research cancelled by user {user} via interrupt queue.")
  522                  break
  523              # Add the interrupt query as a new user message to the research conversation history
  524              logger.info(
  525                  f"Continuing research for user {user} with the previous {len(previous_iterations)} iterations and new instruction: {interrupt_query}"
  526              )
  527              previous_iterations_history = construct_iteration_history(
  528                  previous_iterations, query, query_images, query_files
  529              )
  530              research_conversation_history += previous_iterations_history
  531              query = interrupt_query
  532              previous_iterations = []
  533  
  534              async for result in send_status_func(f"**Incorporate New Instruction**: {interrupt_query}"):
  535                  yield result
  536  
  537          # Collect all tool calls from apick_next_tool
  538          iterations_to_process: List[ResearchIteration] = []
  539>         async for result in apick_next_tool(
  540              query,
  541              research_conversation_history,
  542              user,
  543              location,
  544              user_name,
  545              agent,
  546              previous_iterations,
  547              MAX_ITERATIONS,
```

## AG003 khoj-ai/khoj src/khoj/routers/research.py:627

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/routers/research.py#L627

> call to `execute_tool` inside 2 nested loops (lines 511, 626); calls multiply

```python
  603                              tracer=tracer,
  604                          ):
  605                              if isinstance(res, dict) and ChatEvent.STATUS in res:
  606                                  yield res[ChatEvent.STATUS]
  607                              elif isinstance(res, OperatorRun):
  608                                  result.operator_results = res
  609                                  iteration.operatorContext = result.operator_results
  610                                  if res.webpages:
  611                                      if not result.online_results.get(iteration.query):
  612                                          result.online_results[iteration.query] = {"webpages": res.webpages}
  613                                      elif not result.online_results[iteration.query].get("webpages"):
  614                                          result.online_results[iteration.query]["webpages"] = res.webpages
  615                                      else:
  616                                          result.online_results[iteration.query]["webpages"] += res.webpages
  617                                      iteration.onlineContext = result.online_results
  618                      except Exception as e:
  619                          iteration.warning = f"Error operating browser: {e}"
  620                          logger.error(iteration.warning, exc_info=True)
  621                  streaming_results.append((iteration, result))
  622  
  623              # Execute parallelizable tools in parallel
  624              parallel_results = []
  625              if parallel_iterations:
  626                  tasks = [
  627>                     execute_tool(
  628                          iteration=iteration,
  629                          user=user,
  630                          conversation_id=conversation_id,
  631                          previous_iterations=previous_iterations,
  632                          location=location,
  633                          query_images=query_images,
  634                          query_files=query_files,
  635                          max_document_searches=max_document_searches,
```

## AG003 khoj-ai/khoj src/khoj/database/management/commands/manage_memories.py:130

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/database/management/commands/manage_memories.py#L130

> call to `Command.process_conversation_batch` inside 2 nested loops (lines 106, 128); calls multiply

```python
  106          for user in users:
  107              # Check if user already processed in checkpoint
  108              if not force and user.id in checkpoint.get("processed_users", []):
  109                  self.stdout.write(f"Skipping already processed user: {user.username}")
  110                  continue
  111  
  112              self.stdout.write(f"\nProcessing user: {user.username} (ID: {user.id})")
  113  
  114              # Get conversations for this user
  115              conversations = await self.get_user_conversations(user, cutoff_date, checkpoint, force)
  116  
  117              if not conversations:
  118                  self.stdout.write(f"  No conversations to process for {user.username}")
  119                  # Mark user as processed
  120                  if apply:
  121                      await self.update_checkpoint(checkpoint, user_id=user.id)
  122                  continue
  123  
  124              self.stdout.write(f"  Found {len(conversations)} conversations to process")
  125  
  126              # Process conversations in batches
  127              user_memories = 0
  128              for i in range(0, len(conversations), batch_size):
  129                  batch = conversations[i : i + batch_size]
  130>                 batch_memories = await self.process_conversation_batch(user, batch, apply, checkpoint)
  131                  user_memories += batch_memories
  132                  total_conversations += len(batch)
  133  
  134                  # Update progress
  135                  progress = min(i + batch_size, len(conversations))
  136                  self.stdout.write(
  137                      f"    Processed {progress}/{len(conversations)} conversations, generated {batch_memories} memories"
  138                  )
```

## AG003 khoj-ai/khoj src/khoj/routers/research.py:587

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/routers/research.py#L587

> call to `operate_environment` inside 2 nested loops (lines 511, 579); calls multiply

```python
  563  
  564          # Multi-turn tools that stream their execution
  565          streaming_tools = {ConversationCommand.OperateComputer}
  566          if iterations_to_process:
  567              # Separate streaming tools that need real-time status updates
  568              # from parallelizable tools that can batch their status messages
  569              streaming_iterations: list[ResearchIteration] = []
  570              parallel_iterations: list[ResearchIteration] = []
  571              for iteration in iterations_to_process:
  572                  if isinstance(iteration.query, ToolCall) and iteration.query.name in streaming_tools:
  573                      streaming_iterations.append(iteration)
  574                  else:
  575                      parallel_iterations.append(iteration)
  576  
  577              # Execute streaming tools sequentially for real-time status updates
  578              streaming_results: list[tuple[ResearchIteration, ToolExecutionResult]] = []
  579              for iteration in streaming_iterations:
  580                  result = ToolExecutionResult()
  581                  if (
  582                      isinstance(iteration.query, ToolCall)
  583                      and iteration.query.name == ConversationCommand.OperateComputer
  584                  ):
  585                      try:
  586                          # Execute OperateComputer
  587>                         async for res in operate_environment(
  588                              **iteration.query.args,
  589                              user=user,
  590                              conversation_log=construct_tool_chat_history(
  591                                  previous_iterations, ConversationCommand.Operator
  592                              ),
  593                              location_data=location,
  594                              previous_trajectory=previous_iterations[-1].operatorContext
  595                              if previous_iterations
```

## AG003 khoj-ai/khoj src/khoj/database/management/commands/manage_memories.py:263

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/database/management/commands/manage_memories.py#L263

> call to `extract_facts_from_query` inside 2 nested loops (lines 193, 218); calls multiply

```python
  239                          )
  240  
  241                      if not q or not q.strip():
  242                          i += 1
  243                          continue
  244  
  245                      # Get unique recent and long term relevant memories
  246                      recent_memories = await UserMemoryAdapters.pull_memories(user=user, agent=agent)
  247                      long_term_memories = await UserMemoryAdapters.search_memories(query=q, user=user, agent=agent)
  248                      relevant_memories = list({m.id: m for m in recent_memories + long_term_memories}.values())
  249  
  250                      if apply:
  251                          # Ensure agent is fully loaded with its chat_model
  252                          if agent:
  253  
  254                              @sync_to_async
  255                              def load_agent_with_chat_model():
  256                                  # Force load the chat_model relationship
  257                                  _ = agent.chat_model
  258                                  return agent
  259  
  260                              agent = await load_agent_with_chat_model()
  261  
  262                          # Update memories based on latest conversation turn
  263>                         memory_updates = await extract_facts_from_query(
  264                              user=user,
  265                              conversation_history=history,
  266                              existing_facts=relevant_memories,
  267                              agent=agent,
  268                              tracer={},
  269                          )
  270  
  271                          # Save new memories
```

## AG004 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/api/features/onboarding_dump/brain_dump_eval.py:191

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/api/features/onboarding_dump/brain_dump_eval.py#L191

> call to `evaluate_transcript` runs once per item of a collection

```python
  167          passed=bool(scored)
  168          and len(scored) == len(results)
  169          and pooled.wer < WER_RELEASE_GATE
  170          and (quality_gate is None or quality_gate.passed),
  171          # Reference-less audio that the gate manifest claims is deliberate
  172          # (silence, noise) is the gate's input, not a corpus mistake.
  173          audio_without_reference=[
  174              name
  175              for name in discovery.audio_without_reference
  176              if manifest is None or name not in manifest
  177          ],
  178          reference_without_audio=discovery.reference_without_audio,
  179          quality_gate=quality_gate,
  180      )
  181  
  182  
  183  async def _score_quality_gate(
  184      directory: Path,
  185      discovery: PairDiscovery,
  186      scored: list[FileResult],
  187      manifest: dict[str, brain_dump_gate_eval.GateExpectation],
  188  ) -> GateReport:
  189      """Run the real quality gate over everything the manifest covers."""
  190      results = [
  191>         await brain_dump_gate_eval.evaluate_transcript(
  192              result.name, manifest.get(result.name, "pass"), result.transcript
  193          )
  194          for result in scored
  195      ]
  196      gate_only = brain_dump_gate_eval.discover_gate_only(
  197          directory, manifest, {pair.name for pair in discovery.pairs}, AUDIO_EXTENSIONS
  198      )
  199      results += [
```

## AG004 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/copilot/optimize_blocks.py:48

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/copilot/optimize_blocks.py#L48

> LLM call (openai.chat) runs once per item of a collection

```python
   24  # Rate-limit delay between sequential LLM calls (seconds)
   25  _RATE_LIMIT_DELAY = 0.5
   26  # Maximum tokens for optimized description generation
   27  _MAX_DESCRIPTION_TOKENS = 150
   28  # Model for generating optimized descriptions (fast, cheap)
   29  _MODEL = "gpt-4o-mini"
   30  
   31  
   32  async def _optimize_descriptions(blocks: list[dict[str, str]]) -> dict[str, str]:
   33      """Call the shared OpenAI client to rewrite each block description."""
   34      client = get_openai_client()
   35      if client is None:
   36          logger.error(
   37              "No OpenAI client configured, skipping block description optimization"
   38          )
   39          return {}
   40  
   41      results: dict[str, str] = {}
   42      for block in blocks:
   43          block_id = block["id"]
   44          block_name = block["name"]
   45          description = block["description"]
   46  
   47          try:
   48>             response = await client.chat.completions.create(
   49                  model=_MODEL,
   50                  messages=[
   51                      {"role": "system", "content": SYSTEM_PROMPT},
   52                      {
   53                          "role": "user",
   54                          "content": f"Block name: {block_name}\nDescription: {description}",
   55                      },
   56                  ],
```

## AG004 pydantic/pydantic-ai scripts/verify_vertex_gcs_all_types.py:75

https://github.com/pydantic/pydantic-ai/blob/69ea1e57201ed59e7d30fbe4a7590d193acecce0/scripts/verify_vertex_gcs_all_types.py#L75

> call to `test_file_type` runs once per item of a collection

```python
   51                  description=f'Gets a {file_type}',
   52                  parameters=Schema(type='OBJECT', properties={}),
   53              )
   54          ])
   55      ]
   56  
   57      try:
   58          response = await client.aio.models.generate_content(
   59              model='gemini-2.5-flash',
   60              contents=contents,
   61              config={'tools': tools},
   62          )
   63          text = response.text[:150] if response.text else '(no text)'
   64          print(f'  {file_type}: OK — {text}')
   65      except Exception as e:
   66          print(f'  {file_type}: FAILED — {type(e).__name__}: {e}')
   67  
   68  
   69  async def main() -> None:
   70      print(f'Vertex AI tool results with gs:// URIs')
   71      print(f'Project: {os.environ.get("GOOGLE_PROJECT")}')
   72      print()
   73  
   74      for file_type, (gcs_uri, mime_type) in FILES.items():
   75>         await test_file_type(file_type, gcs_uri, mime_type)
   76  
   77  
   78  if __name__ == '__main__':
   79      asyncio.run(main())
```

## AG004 khoj-ai/khoj src/khoj/processor/tools/online_search.py:495

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/processor/tools/online_search.py#L495

> call to `extract_from_webpage` runs once per item of a collection

```python
  471          user,
  472          send_status_func=send_status_func,
  473          agent=agent,
  474          relevant_memories=relevant_memories,
  475          tracer=tracer,
  476      ):
  477          yield result
  478  
  479  
  480  async def read_webpages_content(
  481      query: str,
  482      urls: List[str],
  483      user: KhojUser,
  484      send_status_func: Optional[Callable] = None,
  485      agent: Agent = None,
  486      relevant_memories: List[UserMemory] = None,
  487      tracer: dict = {},
  488  ):
  489      logger.info(f"Reading web pages at: {urls}")
  490      if send_status_func:
  491          webpage_links_str = "\n- " + "\n- ".join(list(urls))
  492          async for event in send_status_func(f"**Browsing**: {webpage_links_str}"):
  493              yield {ChatEvent.STATUS: event}
  494      tasks = [
  495>         extract_from_webpage(url, {query}, relevant_memories=relevant_memories, user=user, agent=agent, tracer=tracer)
  496          for url in urls
  497      ]
  498      results = await asyncio.gather(*tasks)
  499  
  500      response: Dict[str, Dict] = defaultdict(dict)
  501      response[query]["webpages"] = [
  502          {"query": qs.pop(), "link": url, "snippet": extract} for qs, url, extract in results if extract is not None
  503      ]
```

## AG004 mem0ai/mem0 examples/misc/multillm_memory.py:168

https://github.com/mem0ai/mem0/blob/b7ad69afda6b6ed030347c66d48a13e4de9dec08/examples/misc/multillm_memory.py#L168

> call to `research_with_specialist` runs once per item of a collection

```python
  144          {
  145              "stage": "Product Documentation",
  146              "specialist": "writer",
  147              "task": "Based on the technical analysis, write a clear product overview and user onboarding guide for our SaaS platform.",
  148          },
  149          {
  150              "stage": "Market Analysis",
  151              "specialist": "data_analyst",
  152              "task": "Analyze market trends and pricing strategies for our SaaS platform. What metrics should we track?",
  153          },
  154          {
  155              "stage": "Strategic Decision",
  156              "specialist": "tech_analyst",
  157              "task": "Given our technical architecture, documentation, and market analysis - what should be our MVP feature priority?",
  158          },
  159      ]
  160  
  161      logger.info("AI Research Team: Building a SaaS Product")
  162  
  163      # Execute research pipeline
  164      for i, step in enumerate(research_pipeline, 1):
  165          logger.info(f"\nStage {i}: {step['stage']}")
  166          logger.info(f"Specialist: {step['specialist']}")
  167  
  168>         result = research_with_specialist(step["task"], step["specialist"], project)
  169          logger.info(f"Task: {step['task']}")
  170          logger.info(f"Result: {result[:200]}...\n")
  171  
  172      show_team_knowledge(project)
  173  
  174  
  175  if __name__ == "__main__":
  176      logger.info("Multi-LLM Research Team")
```

## AG004 Significant-Gravitas/AutoGPT autogpt_platform/backend/scripts/backfill_store_sub_headings.py:139

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/scripts/backfill_store_sub_headings.py#L139

> LLM call (openai.chat) runs once per item of a collection

```python
  115          FROM platform."StoreListingVersion"
  116          WHERE {BLANK_SUB_HEADING} AND "isDeleted" = false
  117          {status_clause}
  118          ORDER BY "createdAt" DESC
  119          {limit_clause}
  120          """
  121      )
  122      return [(r["id"], r["name"], r["description"]) for r in rows]
  123  
  124  
  125  async def generate_sub_headings(
  126      rows: list[tuple[str, str, str]], max_length: int
  127  ) -> list[tuple[str, str, str, str]]:
  128      from backend.util.clients import get_openai_client
  129  
  130      client = get_openai_client()
  131      if client is None:
  132          raise SystemExit("No OpenAI client configured (OPENAI_API_KEY unset)")
  133  
  134      system_prompt = SYSTEM_PROMPT.format(max_length=max_length)
  135      proposals: list[tuple[str, str, str, str]] = []
  136      for index, (row_id, name, description) in enumerate(rows, start=1):
  137          try:
  138              response = await asyncio.wait_for(
  139>                 client.chat.completions.create(
  140                      model=MODEL,
  141                      messages=[
  142                          {"role": "system", "content": system_prompt},
  143                          {
  144                              "role": "user",
  145                              "content": f"Name: {name}\nDescription: {description}",
  146                          },
  147                      ],
```

## AG004 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/copilot/graphiti/reranker.py:77

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/copilot/graphiti/reranker.py#L77

> LLM call (openai.chat) runs once per item of a collection

```python
   53                      role="system",
   54                      content=(
   55                          "You are an expert tasked with determining whether the "
   56                          "passage is relevant to the query"
   57                      ),
   58                  ),
   59                  ChatCompletionUserMessageParam(
   60                      role="user",
   61                      content=f"""
   62                             Respond with "True" if PASSAGE is relevant to QUERY and "False" otherwise.
   63                             <PASSAGE>
   64                             {passage}
   65                             </PASSAGE>
   66                             <QUERY>
   67                             {query}
   68                             </QUERY>
   69                             """,
   70                  ),
   71              ]
   72              for passage in passages
   73          ]
   74          try:
   75              responses = await semaphore_gather(
   76                  *[
   77>                     self.client.chat.completions.create(
   78                          model=self.config.model or DEFAULT_MODEL,
   79                          messages=openai_messages,
   80                          temperature=0,
   81                          max_tokens=MIN_COMPLETION_TOKENS,
   82                          logit_bias={"6432": 1, "7983": 1},
   83                          logprobs=True,
   84                          top_logprobs=2,
   85                      )
```

## AG004 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/api/features/onboarding_dump/brain_dump_eval.py:200

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/api/features/onboarding_dump/brain_dump_eval.py#L200

> call to `evaluate_gate_only` runs once per item of a collection

```python
  176              if manifest is None or name not in manifest
  177          ],
  178          reference_without_audio=discovery.reference_without_audio,
  179          quality_gate=quality_gate,
  180      )
  181  
  182  
  183  async def _score_quality_gate(
  184      directory: Path,
  185      discovery: PairDiscovery,
  186      scored: list[FileResult],
  187      manifest: dict[str, brain_dump_gate_eval.GateExpectation],
  188  ) -> GateReport:
  189      """Run the real quality gate over everything the manifest covers."""
  190      results = [
  191          await brain_dump_gate_eval.evaluate_transcript(
  192              result.name, manifest.get(result.name, "pass"), result.transcript
  193          )
  194          for result in scored
  195      ]
  196      gate_only = brain_dump_gate_eval.discover_gate_only(
  197          directory, manifest, {pair.name for pair in discovery.pairs}, AUDIO_EXTENSIONS
  198      )
  199      results += [
  200>         await brain_dump_gate_eval.evaluate_gate_only(path, manifest[path.stem])
  201          for path in gate_only
  202      ]
  203      return brain_dump_gate_eval.build_report(
  204          results, [result.name for result in scored], manifest
  205      )
  206  
  207  
  208  async def evaluate_pair(
```

## AG004 khoj-ai/khoj src/khoj/processor/tools/online_search.py:166

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/processor/tools/online_search.py#L166

> call to `extract_from_webpage` runs once per item of a collection

```python
  142      webpages: Dict[str, Dict] = {}
  143      for subquery in response_dict:
  144          if "answerBox" in response_dict[subquery]:
  145              continue
  146          for idx, organic in enumerate(response_dict[subquery].get("organic") or []):
  147              link = organic.get("link")
  148              if link in webpages and idx < max_webpages_to_read:
  149                  webpages[link]["queries"].add(subquery)
  150              # Content of web pages can be directly available when Exa is used for search.
  151              elif idx < max_webpages_to_read:
  152                  webpages[link] = {"queries": {subquery}, "content": organic.get("content")}
  153              # Only keep webpage content for up to max_webpages_to_read organic results.
  154              if idx >= max_webpages_to_read and not is_none_or_empty(organic.get("content")):
  155                  organic["content"] = None
  156                  response_dict[subquery]["organic"][idx] = organic
  157  
  158      # Read, extract relevant info from the retrieved web pages
  159      if webpages:
  160          logger.info(f"Reading web pages at: {webpages.keys()}")
  161          if send_status_func:
  162              webpage_links_str = "\n- " + "\n- ".join(webpages.keys())
  163              async for event in send_status_func(f"**Browsing**: {webpage_links_str}"):
  164                  yield {ChatEvent.STATUS: event}
  165      tasks = [
  166>         extract_from_webpage(
  167              link,
  168              data["queries"],
  169              data.get("content"),
  170              relevant_memories=relevant_memories,
  171              user=user,
  172              agent=agent,
  173              tracer=tracer,
  174          )
```

## AG004 khoj-ai/khoj src/khoj/routers/helpers.py:1703

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/routers/helpers.py#L1703

> call to `send_message_to_model` runs once per item of a collection

```python
 1679      models_to_try = [primary_chat_model] + fallback_models
 1680  
 1681      last_exception: Optional[Exception] = None
 1682      for i, chat_model in enumerate(models_to_try):
 1683          is_last_model = i == len(models_to_try) - 1
 1684  
 1685          # Prepare messages for this specific model
 1686          max_tokens = await ConversationAdapters.aget_max_context_size(chat_model, user)
 1687          truncated_messages = generate_chatml_messages_with_context(
 1688              user_message=query,
 1689              query_files=query_files,
 1690              query_images=query_images,
 1691              context_message=context,
 1692              relevant_memories=relevant_memories,
 1693              chat_history=chat_history,
 1694              system_message=system_message,
 1695              model_name=chat_model.name,
 1696              model_type=chat_model.model_type,
 1697              tokenizer_name=chat_model.tokenizer,
 1698              max_prompt_size=max_tokens,
 1699              vision_enabled=chat_model.vision_enabled if not query_images else vision_available,
 1700          )
 1701  
 1702          try:
 1703>             return send_message_to_model(
 1704                  chat_model=chat_model,
 1705                  truncated_messages=truncated_messages,
 1706                  response_type=response_type,
 1707                  response_schema=response_schema,
 1708                  tools=tools,
 1709                  deepthought=deepthought,
 1710                  tracer=tracer,
 1711              )
```

## AG004 pydantic/pydantic-ai scripts/verify_vertex_gcs.py:63

https://github.com/pydantic/pydantic-ai/blob/69ea1e57201ed59e7d30fbe4a7590d193acecce0/scripts/verify_vertex_gcs.py#L63

> call to `test_vertex_with_gcs_uri` runs once per item of a collection

```python
   39          response = await client.aio.models.generate_content(
   40              model='gemini-2.5-flash',
   41              contents=[
   42                  Content(
   43                      role='user',
   44                      parts=[
   45                          Part(text=prompt),
   46                          Part(file_data={'file_uri': gcs_uri, 'mime_type': mime_type}),
   47                      ],
   48                  )
   49              ],
   50          )
   51          text = response.text[:100] if response.text else '(no text)'
   52          print(f'  {file_type}: OK — {text}')
   53      except Exception as e:
   54          print(f'  {file_type}: FAILED — {type(e).__name__}: {e}')
   55  
   56  
   57  async def main() -> None:
   58      print(f'Project: {os.environ.get("GOOGLE_PROJECT")}')
   59      print(f'Location: {os.environ.get("GOOGLE_LOCATION", "global")}')
   60      print()
   61  
   62      for file_type, (gcs_uri, mime_type) in GCS_FILES.items():
   63>         await test_vertex_with_gcs_uri(file_type, gcs_uri, mime_type)
   64  
   65  
   66  if __name__ == '__main__':
   67      asyncio.run(main())
```

## AG005 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/copilot/sdk/service.py:4650

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/copilot/sdk/service.py#L4650

> `stream_chat_completion_sdk` makes LLM calls and calls itself, with no depth parameter to stop it

```python
 4626          return query_message
 4627      return notice + query_message if notice else query_message
 4628  
 4629  
 4630  def _maybe_prepend_seen_capabilities(
 4631      session: ChatSession,
 4632      is_user_message: bool,
 4633      query_message: str,
 4634  ) -> str:
 4635      """Prepend the per-turn ``<seen_capabilities>`` notice, if any.
 4636  
 4637      Derived from the tool calls persisted in ``session.messages`` so the
 4638      model is told which ids it already described / ran and which skills it
 4639      already loaded instead of re-discovering them after a resume or a
 4640      compaction (SECRT-2791). Same query-only contract as the skills-update
 4641      notice: never persisted, re-derived every turn, no-op for non-user
 4642      turns and for a first turn with no history.
 4643      """
 4644      if not is_user_message:
 4645          return query_message
 4646      notice = build_seen_capabilities_notice(session)
 4647      return notice + query_message if notice else query_message
 4648  
 4649  
 4650> async def stream_chat_completion_sdk(  # pyright: ignore[reportGeneralTypeIssues]
 4651      session_id: str,
 4652      message: str | None = None,
 4653      is_user_message: bool = True,
 4654      user_id: str | None = None,
 4655      session: ChatSession | None = None,
 4656      file_ids: list[str] | None = None,
 4657      permissions: "CopilotPermissions | None" = None,
 4658      envelope: "TurnEnvelope | None" = None,
```

## AG006 browser-use/browser-use examples/custom-functions/cua.py:230

https://github.com/browser-use/browser-use/blob/c75e8476e26d18b7617643bc2ae082fae8eae431/examples/custom-functions/cua.py#L230

> LLM call (openai.responses) sets no output-token cap

```python
  206  		print(f'📸 Screenshot captured (base64 length: {len(screenshot_b64)} chars)')
  207  
  208  		# Debug: Check screenshot dimensions
  209  		image = Image.open(BytesIO(base64.b64decode(screenshot_b64)))
  210  		print(f'📏 Screenshot actual dimensions: {image.size[0]}x{image.size[1]}')
  211  
  212  		# rescale the screenshot to the viewport size
  213  		image = image.resize((page_info.viewport_width, page_info.viewport_height))
  214  		# Save as PNG to bytes buffer
  215  		buffer = BytesIO()
  216  		image.save(buffer, format='PNG')
  217  		buffer.seek(0)
  218  		# Convert to base64
  219  		screenshot_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
  220  		print(f'📸 Rescaled screenshot to viewport size: {page_info.viewport_width}x{page_info.viewport_height}')
  221  
  222  		client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
  223  		print('🔄 Sending request to OpenAI CUA...')
  224  
  225  		prompt = f"""
  226          You will be given an action to execute and screenshot of the current screen. 
  227          Output one computer_call object that will achieve this goal.
  228          Goal: {params.description}
  229          """
  230> 		response = await client.responses.create(
  231  			model='computer-use-preview',
  232  			tools=[
  233  				{
  234  					'type': 'computer_use_preview',
  235  					'display_width': page_info.viewport_width,
  236  					'display_height': page_info.viewport_height,
  237  					'environment': 'browser',
  238  				}
```

## AG006 khoj-ai/khoj src/khoj/processor/operator/operator_agent_openai.py:218

https://github.com/khoj-ai/khoj/blob/ae229ca894c0b80ad84664afcfdde523b5e87057/src/khoj/processor/operator/operator_agent_openai.py#L218

> LLM call (openai.responses) sets no output-token cap

```python
  194          self.messages += [AgentMessage(role="environment", content=agent_action.action_results)]
  195  
  196      async def summarize(self, current_state: EnvState, summarize_prompt: str = None) -> str:
  197          summarize_prompt = summarize_prompt or self.summarize_prompt
  198          self.messages.append(AgentMessage(role="user", content=summarize_prompt))
  199          response = await self._call_model(self.vision_model, summarize_prompt, [])
  200          self.messages += [AgentMessage(role="assistant", content=response.output)]
  201          if not self.messages:
  202              return "No actions to summarize."
  203          return self._compile_response(self.messages[-1].content)
  204  
  205      async def _call_model(self, model: ChatModel, system_prompt, tools) -> Response:
  206          client = get_openai_async_client(model.ai_model_api.api_key, model.ai_model_api.api_base_url)
  207          if tools:
  208              model_name = "computer-use-preview"
  209          else:
  210              model_name = model.name
  211  
  212          # Format messages for OpenAI API
  213          messages_for_api = self._format_message_for_api(self.messages)
  214          # format messages for summary if model is not computer-use-preview
  215          if model_name != "computer-use-preview":
  216              messages_for_api = self._format_messages_for_summary(messages_for_api)
  217  
  218>         response: Response = await client.responses.create(
  219              model=model_name,
  220              input=messages_for_api,
  221              instructions=system_prompt,
  222              tools=tools,
  223              parallel_tool_calls=False,
  224              truncation="auto",
  225          )
  226  
```

## AG006 qodo-ai/pr-agent pr_agent/algo/ai_handlers/openai_ai_handler.py:56

https://github.com/qodo-ai/pr-agent/blob/cf76f708a1ac58cc8d0e26dde26fa53cc4b8819e/pr_agent/algo/ai_handlers/openai_ai_handler.py#L56

> LLM call (openai.chat) sets no output-token cap

```python
   32          except AttributeError as e:
   33              raise ValueError("OpenAI key is required") from e
   34  
   35      @property
   36      def deployment_id(self):
   37          """
   38          Returns the deployment ID for the OpenAI API.
   39          """
   40          return get_settings().get("OPENAI.DEPLOYMENT_ID", None)
   41  
   42      @retry(
   43          retry=retry_if_exception_type(openai.APIError) & retry_if_not_exception_type(
   44              (openai.RateLimitError, openai.BadRequestError, openai.UnprocessableEntityError)
   45          ),
   46          stop=stop_after_attempt(OPENAI_RETRIES),
   47      )
   48      async def chat_completion(self, model: str, system: str, user: str, temperature: float = 0.2, img_path: str = None):
   49          try:
   50              if img_path:
   51                  get_logger().warning(f"Image path is not supported for OpenAIHandler. Ignoring image path: {img_path}")
   52              get_logger().info("System: ", system)
   53              get_logger().info("User: ", user)
   54              messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
   55              client = AsyncOpenAI()
   56>             chat_completion = await client.chat.completions.create(
   57                  model=model,
   58                  messages=messages,
   59                  temperature=temperature,
   60              )
   61              resp = chat_completion.choices[0].message.content
   62              finish_reason = chat_completion.choices[0].finish_reason
   63              usage = chat_completion.usage
   64              get_logger().info("AI response", response=resp, messages=messages, finish_reason=finish_reason,
```

## AG006 mem0ai/mem0 examples/misc/multillm_memory.py:87

https://github.com/mem0ai/mem0/blob/b7ad69afda6b6ed030347c66d48a13e4de9dec08/examples/misc/multillm_memory.py#L87

> LLM call (litellm) sets no output-token cap

```python
   63          return knowledge
   64      return "Team Knowledge Base: Empty - starting fresh research"
   65  
   66  
   67  def research_with_specialist(task: str, specialist: str, project_id: str) -> str:
   68      """Assign research task to specialist with access to team knowledge"""
   69  
   70      if specialist not in RESEARCH_TEAM:
   71          return f"Unknown specialist. Available: {list(RESEARCH_TEAM.keys())}"
   72  
   73      # Get team's accumulated knowledge
   74      team_knowledge = get_team_knowledge(task, project_id)
   75  
   76      # Specialist role and model
   77      spec_info = RESEARCH_TEAM[specialist]
   78  
   79      system_prompt = f"""You are the {spec_info['role']}.
   80  
   81  {team_knowledge}
   82  
   83  Build upon the team's existing research. Reference previous findings when relevant.
   84  Provide actionable insights in your area of expertise."""
   85  
   86      # Call the specialist's model
   87>     response = completion(
   88          model=spec_info["model"],
   89          messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": task}],
   90      )
   91  
   92      result = response.choices[0].message.content
   93  
   94      # Store research in shared knowledge base using both user_id and agent_id
   95      research_entry = [{"role": "user", "content": f"Task: {task}"}, {"role": "assistant", "content": result}]
```

## AG006 browser-use/browser-use browser_use/llm/groq/chat.py:229

https://github.com/browser-use/browser-use/blob/c75e8476e26d18b7617643bc2ae082fae8eae431/browser_use/llm/groq/chat.py#L229

> LLM call (openai.chat) sets no output-token cap

```python
  205  		if not message.tool_calls:
  206  			raise ModelProviderError(
  207  				message='No tool calls in response',
  208  				status_code=500,
  209  				model=self.name,
  210  			)
  211  
  212  		arguments = message.tool_calls[0].function.arguments
  213  		if isinstance(arguments, str):
  214  			return output_format.model_validate_json(arguments)
  215  		return output_format.model_validate(arguments)
  216  
  217  	async def _invoke_with_tool_calling(self, groq_messages, output_format: type[T], schema) -> ChatCompletion:
  218  		"""Handle structured output using tool calling."""
  219  		tool = ChatCompletionToolParam(
  220  			function={
  221  				'name': output_format.__name__,
  222  				'description': f'Extract information in the format of {output_format.__name__}',
  223  				'parameters': schema,
  224  			},
  225  			type='function',
  226  		)
  227  		tool_choice: ChatCompletionToolChoiceOptionParam = 'required'
  228  
  229> 		return await self.get_client().chat.completions.create(
  230  			model=self.model,
  231  			messages=groq_messages,
  232  			temperature=self.temperature,
  233  			top_p=self.top_p,
  234  			seed=self.seed,
  235  			tools=[tool],
  236  			tool_choice=tool_choice,
  237  			service_tier=self.service_tier,
```

## AG006 microsoft/TaskWeaver taskweaver/llm/groq.py:62

https://github.com/microsoft/TaskWeaver/blob/d44ddef23f90059fb17999d3095db4240e98f955/taskweaver/llm/groq.py#L62

> LLM call (openai.chat) sets no output-token cap

```python
   38  
   39          if GroqService.client is None:
   40              try:
   41                  from groq import Groq
   42  
   43                  GroqService.client = Groq(
   44                      api_key=self.config.api_key,
   45                  )
   46              except Exception:
   47                  raise Exception(
   48                      "Package groq is required for using Groq API. ",
   49                  )
   50  
   51      def chat_completion(
   52          self,
   53          messages: List[ChatMessageType],
   54          use_backup_engine: bool = False,
   55          stream: bool = True,
   56          temperature: Optional[float] = None,
   57          max_tokens: Optional[int] = None,
   58          top_p: Optional[float] = None,
   59          stop: Optional[List[str]] = None,
   60          **kwargs: Any,
   61      ) -> Generator[ChatMessageType, None, None]:
   62>         response = GroqService.client.chat.completions.create(
   63              messages=messages,
   64              model=self.config.model,
   65          )
   66  
   67          yield format_chat_message("assistant", response.choices[0].message.content)
   68  
   69      def get_embeddings(self, strings: List[str]) -> List[List[float]]:
   70          pass
```

## AG006 camel-ai/camel camel/models/reward/nemotron_model.py:72

https://github.com/camel-ai/camel/blob/24fde60ad739b4be8f8f533fea9ba54256fbc4a2/camel/models/reward/nemotron_model.py#L72

> LLM call (openai.chat) sets no output-token cap

```python
   48          super().__init__(model_type, api_key, url)
   49          self._client = OpenAI(
   50              timeout=180,
   51              max_retries=3,
   52              base_url=self.url,
   53              api_key=self.api_key,
   54          )
   55  
   56      @api_keys_required(
   57          [
   58              (None, "NVIDIA_API_KEY"),
   59          ]
   60      )
   61      def evaluate(self, messages: List[Dict[str, str]]) -> Dict[str, float]:
   62          r"""Evaluate the messages using the Nemotron model.
   63  
   64          Args:
   65              messages (List[Dict[str, str]]): A list of messages where each
   66                  message is a dictionary format.
   67  
   68          Returns:
   69              Dict[str, float]:  A dictionary mapping score types to their
   70                  values.
   71          """
   72>         response = self._client.chat.completions.create(
   73              messages=messages,  # type: ignore[arg-type]
   74              model=self.model_type,
   75          )
   76          scores = self._parse_scores(response)
   77          return scores
   78  
   79      def get_scores_types(self) -> List[str]:
   80          r"""Get the list of score types that the reward model can return.
```

## AG006 browser-use/browser-use browser_use/llm/openrouter/chat.py:191

https://github.com/browser-use/browser-use/blob/c75e8476e26d18b7617643bc2ae082fae8eae431/browser_use/llm/openrouter/chat.py#L191

> LLM call (openai.chat) sets no output-token cap

```python
  167  					top_p=self.top_p,
  168  					seed=self.seed,
  169  					extra_headers=extra_headers,
  170  					extra_body=self.extra_body,
  171  				)
  172  
  173  				choice = self._get_first_choice(response)
  174  				usage = self._get_usage(response)
  175  				return ChatInvokeCompletion(
  176  					completion=choice.message.content or '',
  177  					usage=usage,
  178  				)
  179  
  180  			else:
  181  				# Create a JSON schema for structured output
  182  				schema = SchemaOptimizer.create_optimized_json_schema(output_format)
  183  
  184  				response_format_schema: JSONSchema = {
  185  					'name': 'agent_output',
  186  					'strict': True,
  187  					'schema': schema,
  188  				}
  189  
  190  				# Return structured response
  191> 				response = await self.get_client().chat.completions.create(
  192  					model=self.model,
  193  					messages=openrouter_messages,
  194  					temperature=self.temperature,
  195  					top_p=self.top_p,
  196  					seed=self.seed,
  197  					response_format=ResponseFormatJSONSchema(
  198  						json_schema=response_format_schema,
  199  						type='json_schema',
```

## AG006 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/executor/simulator.py:217

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/executor/simulator.py#L217

> LLM call (openai.chat) sets no output-token cap

```python
  193      # Local backends govern their own context window at launch (e.g.
  194      # OLLAMA_CONTEXT_LENGTH), so we send no per-request num_ctx hint —
  195      # Ollama's OpenAI shim ignores ``options.num_ctx`` anyway.
  196      from backend.copilot.sdk.env import config as chat_cfg
  197  
  198      if chat_cfg.transport.name == "local":
  199          extra_body: dict[str, Any] = {}
  200      else:
  201          # Shallow-copy the constant rather than sharing the reference — see
  202          # the matching pattern in ``baseline/service.py`` and
  203          # ``activity_status_generator.py``. Defends against intermediate
  204          # layers ever mutating ``extra_body`` and corrupting the shared
  205          # module-level dict for every future call.
  206          extra_body = dict(_OPENROUTER_INCLUDE_USAGE_COST)
  207  
  208      model = _simulator_model()
  209      last_error: Exception | None = None
  210      last_parsed: dict[str, Any] | None = None
  211      messages: list[ChatCompletionMessageParam] = [
  212          {"role": "system", "content": system_prompt},
  213          {"role": "user", "content": user_prompt},
  214      ]
  215      for attempt in range(_MAX_JSON_RETRIES):
  216          try:
  217>             response = await client.chat.completions.create(
  218                  model=model,
  219                  temperature=_TEMPERATURE,
  220                  response_format={"type": "json_object"},
  221                  messages=messages,
  222                  extra_body=extra_body,
  223              )
  224              if not response.choices:
  225                  raise ValueError("LLM returned empty choices array")
```

## AG006 browser-use/browser-use browser_use/llm/groq/chat.py:242

https://github.com/browser-use/browser-use/blob/c75e8476e26d18b7617643bc2ae082fae8eae431/browser_use/llm/groq/chat.py#L242

> LLM call (openai.chat) sets no output-token cap

```python
  218  		"""Handle structured output using tool calling."""
  219  		tool = ChatCompletionToolParam(
  220  			function={
  221  				'name': output_format.__name__,
  222  				'description': f'Extract information in the format of {output_format.__name__}',
  223  				'parameters': schema,
  224  			},
  225  			type='function',
  226  		)
  227  		tool_choice: ChatCompletionToolChoiceOptionParam = 'required'
  228  
  229  		return await self.get_client().chat.completions.create(
  230  			model=self.model,
  231  			messages=groq_messages,
  232  			temperature=self.temperature,
  233  			top_p=self.top_p,
  234  			seed=self.seed,
  235  			tools=[tool],
  236  			tool_choice=tool_choice,
  237  			service_tier=self.service_tier,
  238  		)
  239  
  240  	async def _invoke_with_json_schema(self, groq_messages, output_format: type[T], schema) -> ChatCompletion:
  241  		"""Handle structured output using JSON schema."""
  242> 		return await self.get_client().chat.completions.create(
  243  			model=self.model,
  244  			messages=groq_messages,
  245  			temperature=self.temperature,
  246  			top_p=self.top_p,
  247  			seed=self.seed,
  248  			response_format=ResponseFormatResponseFormatJsonSchema(
  249  				json_schema=ResponseFormatResponseFormatJsonSchemaJsonSchema(
  250  					name=output_format.__name__,
```

## AG006 Significant-Gravitas/AutoGPT autogpt_platform/backend/backend/data/tally.py:417

https://github.com/Significant-Gravitas/AutoGPT/blob/4473fbbcb1951471df0a05374d47c93c4e39bea6/autogpt_platform/backend/backend/data/tally.py#L417

> LLM call (openai.chat) sets no output-token cap

```python
  393      )
  394  
  395      # ``_LLM_TIMEOUT`` was sized for OpenRouter latency. Local CPU-only
  396      # Ollama can take 30–120+ seconds for even a small JSON extraction
  397      # (`qwen3:0.6b` on a 4-core VM is typical of the no-API-key install
  398      # target), so the fixed cloud timeout fires before the model finishes
  399      # and every Tally submission raises ``TimeoutError`` under local
  400      # transport. Track the operator's already-tuned
  401      # ``local_request_timeout_s`` instead — the same knob that gates the
  402      # AsyncOpenAI client timeout, so the two stay aligned.
  403      timeout_s = (
  404          chat_cfg.local_request_timeout_s
  405          if chat_cfg.transport.name == "local"
  406          else _LLM_TIMEOUT
  407      )
  408  
  409      messages: list[ChatCompletionUserMessageParam] = [
  410          {
  411              "role": "user",
  412              "content": f"{_EXTRACTION_PROMPT}{formatted_text}{_EXTRACTION_SUFFIX}",
  413          }
  414      ]
  415      try:
  416          response = await asyncio.wait_for(
  417>             client.chat.completions.create(
  418                  model=model,
  419                  messages=messages,
  420                  response_format={"type": "json_object"},
  421                  temperature=0.0,
  422              ),
  423              timeout=timeout_s,
  424          )
  425      except asyncio.TimeoutError:
```

## AG006 mem0ai/mem0 examples/misc/movie_recommendation_grok3.py:55

https://github.com/mem0ai/mem0/blob/b7ad69afda6b6ed030347c66d48a13e4de9dec08/examples/misc/movie_recommendation_grok3.py#L55

> LLM call (openai.chat) sets no output-token cap

```python
   31              "model": "all-MiniLM-L6-v2"  # open embedding model
   32          },
   33      },
   34  }
   35  
   36  # Instantiate memory layer
   37  memory = Memory.from_config(config)
   38  
   39  # Initialize Grok 3 client
   40  grok_client = OpenAI(
   41      api_key=os.getenv("XAI_API_KEY"),
   42      base_url="https://api.x.ai/v1",
   43  )
   44  
   45  
   46  def recommend_movie_with_memory(user_id: str, user_query: str):
   47      # Retrieve prior memory about movies
   48      past_memories = memory.search("movie preferences", filters={"user_id": user_id})
   49  
   50      prompt = user_query
   51      if past_memories["results"]:
   52          prompt += f"\nPreviously, the user mentioned: {[m['memory'] for m in past_memories['results']]}"
   53  
   54      # Generate movie recommendation using Grok 3
   55>     response = grok_client.chat.completions.create(model="grok-3-beta", messages=[{"role": "user", "content": prompt}])
   56      recommendation = response.choices[0].message.content
   57  
   58      # Store conversation in memory
   59      memory.add(
   60          [{"role": "user", "content": user_query}, {"role": "assistant", "content": recommendation}],
   61          user_id=user_id,
   62          metadata={"category": "movie"},
   63      )
```

## AG006 browser-use/browser-use browser_use/llm/groq/chat.py:157

https://github.com/browser-use/browser-use/blob/c75e8476e26d18b7617643bc2ae082fae8eae431/browser_use/llm/groq/chat.py#L157

> LLM call (openai.chat) sets no output-token cap

```python
  133  
  134  					parsed_response = try_parse_groq_failed_generation(e, output_format)
  135  
  136  					logger.debug('Manual error parsing successful ✅')
  137  
  138  					return ChatInvokeCompletion(
  139  						completion=parsed_response,
  140  						usage=None,  # because this is a hacky way to get the outputs
  141  						# TODO: @groq needs to fix their parsers and validators
  142  					)
  143  				except Exception as _:
  144  					raise ModelProviderError(message=str(e), status_code=e.response.status_code, model=self.name) from e
  145  
  146  		except APIError as e:
  147  			raise ModelProviderError(message=e.message, model=self.name) from e
  148  		except ModelProviderError:
  149  			# errors we raised ourselves (e.g. from structured-output parsing) already carry the right
  150  			# status code and message, so let them through instead of re-wrapping with the default status
  151  			raise
  152  		except Exception as e:
  153  			raise ModelProviderError(message=str(e), model=self.name) from e
  154  
  155  	async def _invoke_regular_completion(self, groq_messages) -> ChatInvokeCompletion[str]:
  156  		"""Handle regular completion without structured output."""
  157> 		chat_completion = await self.get_client().chat.completions.create(
  158  			messages=groq_messages,
  159  			model=self.model,
  160  			service_tier=self.service_tier,
  161  			temperature=self.temperature,
  162  			top_p=self.top_p,
  163  			seed=self.seed,
  164  		)
  165  		usage = self._get_usage(chat_completion)
```

## AG006 browser-use/browser-use browser_use/llm/openrouter/chat.py:163

https://github.com/browser-use/browser-use/blob/c75e8476e26d18b7617643bc2ae082fae8eae431/browser_use/llm/openrouter/chat.py#L163

> LLM call (openai.chat) sets no output-token cap

```python
  139  
  140  	async def ainvoke(
  141  		self, messages: list[BaseMessage], output_format: type[T] | None = None, **kwargs: Any
  142  	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
  143  		"""
  144  		Invoke the model with the given messages through OpenRouter.
  145  
  146  		Args:
  147  		    messages: List of chat messages
  148  		    output_format: Optional Pydantic model class for structured output
  149  
  150  		Returns:
  151  		    Either a string response or an instance of output_format
  152  		"""
  153  		openrouter_messages = OpenRouterMessageSerializer.serialize_messages(messages)
  154  
  155  		# Set up extra headers for OpenRouter
  156  		extra_headers = {}
  157  		if self.http_referer:
  158  			extra_headers['HTTP-Referer'] = self.http_referer
  159  
  160  		try:
  161  			if output_format is None:
  162  				# Return string response
  163> 				response = await self.get_client().chat.completions.create(
  164  					model=self.model,
  165  					messages=openrouter_messages,
  166  					temperature=self.temperature,
  167  					top_p=self.top_p,
  168  					seed=self.seed,
  169  					extra_headers=extra_headers,
  170  					extra_body=self.extra_body,
  171  				)
```
