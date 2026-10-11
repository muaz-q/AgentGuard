# Findings sampled for hand review

Seed 2026; up to 1000 per rule. Verdicts are recorded in labels.csv.

## AG001 Aider-AI/aider aider/coders/base_coder.py:1373

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/base_coder.py#L1373

> LLM call (litellm) inside `while` loop (line 1358) with no iteration cap

```python
 1349          delay = float(os.environ.get("AIDER_CACHE_KEEPALIVE_DELAY", delay))
 1350          self.next_cache_warm = time.time() + delay
 1351          self.warming_pings_left = self.num_cache_warming_pings
 1352          self.cache_warming_chunks = chunks
 1353  
 1354          if self.cache_warming_thread:
 1355              return
 1356  
 1357          def warm_cache_worker():
 1358              while self.ok_to_warm_cache:
 1359                  time.sleep(1)
 1360                  if self.warming_pings_left <= 0:
 1361                      continue
 1362                  now = time.time()
 1363                  if now < self.next_cache_warm:
 1364                      continue
 1365  
 1366                  self.warming_pings_left -= 1
 1367                  self.next_cache_warm = time.time() + delay
 1368  
 1369                  kwargs = dict(self.main_model.extra_params) or dict()
 1370                  kwargs["max_tokens"] = 1
 1371  
 1372                  try:
 1373>                     completion = litellm.completion(
 1374                          model=self.main_model.name,
 1375                          messages=self.cache_warming_chunks.cacheable_messages(),
 1376                          stream=False,
 1377                          **kwargs,
 1378                      )
 1379                  except Exception as err:
 1380                      self.io.tool_warning(f"Cache warming error: {str(err)}")
 1381                      continue
```

## AG001 Aider-AI/aider aider/models.py:1058

https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/models.py#L1058

> call to `Model.send_completion` inside `while` loop (line 1050) with no iteration cap

```python
 1034              self.github_copilot_token_to_open_ai_key(kwargs["extra_headers"])
 1035  
 1036          res = litellm.completion(**kwargs)
 1037          return hash_object, res
 1038  
 1039      def simple_send_with_retries(self, messages):
 1040          from aider.exceptions import LiteLLMExceptions
 1041  
 1042          litellm_ex = LiteLLMExceptions()
 1043          if "deepseek-reasoner" in self.name:
 1044              messages = ensure_alternating_roles(messages)
 1045          retry_delay = 0.125
 1046  
 1047          if self.verbose:
 1048              dump(messages)
 1049  
 1050          while True:
 1051              try:
 1052                  kwargs = {
 1053                      "messages": messages,
 1054                      "functions": None,
 1055                      "stream": False,
 1056                  }
 1057  
 1058>                 _hash, response = self.send_completion(**kwargs)
 1059                  if not response or not hasattr(response, "choices") or not response.choices:
 1060                      return None
 1061                  res = response.choices[0].message.content
 1062                  from aider.reasoning_tags import remove_reasoning_content
 1063  
 1064                  return remove_reasoning_content(res, self.reasoning_tag)
 1065  
 1066              except litellm_ex.exceptions_tuple() as err:
```

## AG001 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:453

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L453

> LLM call (litellm) inside `while` loop (line 413) with no iteration cap

```python
  429          if not scrape_result.get("error"):
  430              api_scrape_info[current_url] = scrape_result
  431              intermediate_steps.append({"step": f"Scrape URL: {current_url}", "content": scrape_result})
  432          else:
  433              print(f"[WARN] Error in scrape_result for {current_url}: {scrape_result.get('error')}")
  434              intermediate_steps.append({"step": f"Scrape Error for URL: {current_url}", "content": scrape_result.get("error")})
  435              continue  # Skip to the next URL
  436  
  437          # Step 6: Use LLM to extract relevant info and decide if more info is needed
  438          extraction_prompt = f"""The user wants to create a function described as follows: {description}.
  439  You have accumulated the following relevant API information so far:
  440  {accumulated_info}
  441  
  442  You have just scraped the following new API documentation:
  443  {json.dumps(scrape_result)}
  444  
  445  Based on the new information, extract any additional relevant API methods, endpoints, and usage patterns needed to implement the user's function. Indicate whether more information is required by setting 'requires_more_info' to true or false. If any other URLs should be scraped for further information, include them in the 'additional_urls' field."""
  446  
  447          # Chunk the extraction prompt if it's too long
  448          extraction_prompt_chunks = chunk_text(extraction_prompt)
  449          extraction_results = []
  450  
  451          for chunk in extraction_prompt_chunks:
  452              try:
  453>                 extraction_response = completion(
  454                      model="gpt-4o-mini",
  455                      messages=[
  456                          {"role": "system", "content": system_prompt},
  457                          {"role": "user", "content": chunk}
  458                      ],
  459                      response_format=ExtractionInfo
  460                  )
  461                  print(f"[DEBUG] Extraction Response: {extraction_response}")
```

## AG001 openai/swarm examples/customer_service_streaming/main.py:59

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/main.py#L59

> call to `Swarm.deploy` inside `while` loop (line 32) with no iteration cap

```python
   35  
   36              # Check for exit command
   37              if task_input.lower() == 'exit':
   38                  break
   39  
   40              # Use shlex to parse the task description and arguments
   41              task_args = shlex.split(task_input)
   42              task_parser = argparse.ArgumentParser()
   43              task_parser.add_argument("description", type=str, nargs='?', default="")
   44              task_parser.add_argument("--iterate", action="store_true", help="Set the iterate flag for the new task.")
   45              task_parser.add_argument("--evaluate", action="store_true", help="Set the evaluate flag for the new task.")
   46              task_parser.add_argument("--assistant", type=str, default="user_interface", help="Specify the assistant for the new task.")
   47  
   48              # Parse task arguments
   49              task_parsed_args = task_parser.parse_args(task_args)
   50  
   51              # Create and add the new task
   52              new_task = Task(description=task_parsed_args.description,
   53                              iterate=task_parsed_args.iterate,
   54                              evaluate=task_parsed_args.evaluate,
   55                              assistant=task_parsed_args.assistant)
   56              swarm.add_task(new_task)
   57  
   58              # Deploy Swarm with the new task
   59>             swarm.deploy()
   60              swarm.tasks.clear()
   61  
   62      else:
   63          # Load predefined tasks if any
   64          # Deploy the Swarm for predefined tasks
   65          swarm.load_tasks()
   66          swarm.deploy()
   67  
```

## AG002 yoheinakajima/babyagi babyagi/functionz/packs/drafts/react_agent.py:109

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/react_agent.py#L109

> LLM call (litellm) re-sends a history that grows every iteration; input tokens grow quadratically

```python
   85              {"role": "user", "content": input_text},
   86          ]
   87  
   88          # Initialize loop parameters
   89          max_iterations = 5
   90          iteration = 0
   91  
   92          full_reasoning_path = ""
   93  
   94          while iteration < max_iterations:
   95              iteration += 1
   96  
   97              # Update the system prompt with the current function call history
   98              if function_call_history:
   99                  history_str = "\n".join([
  100                      f"- {call['function_name']} with arguments {call['arguments']} produced output: {call['output']}"
  101                      for call in function_call_history
  102                  ])
  103              else:
  104                  history_str = "None"
  105  
  106              chat_context[0]['content'] = system_prompt.replace("{{function_call_history}}", history_str)
  107  
  108              # Call LiteLLM's completion API with the chat context and tools
  109>             response = litellm.completion(
  110                  model="gpt-4-turbo",
  111                  messages=chat_context,
  112                  tools=tools,
  113                  tool_choice="auto",
  114                  max_tokens=1500,
  115                  temperature=0.7
  116              )
  117  
```

## AG002 openai/swarm swarm/core.py:260

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/swarm/core.py#L260

> call to `Swarm.get_chat_completion` re-sends a history that grows every iteration; input tokens grow quadratically

```python
  236          model_override: str = None,
  237          stream: bool = False,
  238          debug: bool = False,
  239          max_turns: int = float("inf"),
  240          execute_tools: bool = True,
  241      ) -> Response:
  242          if stream:
  243              return self.run_and_stream(
  244                  agent=agent,
  245                  messages=messages,
  246                  context_variables=context_variables,
  247                  model_override=model_override,
  248                  debug=debug,
  249                  max_turns=max_turns,
  250                  execute_tools=execute_tools,
  251              )
  252          active_agent = agent
  253          context_variables = copy.deepcopy(context_variables)
  254          history = copy.deepcopy(messages)
  255          init_len = len(messages)
  256  
  257          while len(history) - init_len < max_turns and active_agent:
  258  
  259              # get completion with current history, agent
  260>             completion = self.get_chat_completion(
  261                  agent=active_agent,
  262                  history=history,
  263                  context_variables=context_variables,
  264                  model_override=model_override,
  265                  stream=stream,
  266                  debug=debug,
  267              )
  268              message = completion.choices[0].message
```

## AG002 openai/swarm swarm/core.py:171

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/swarm/core.py#L171

> call to `Swarm.get_chat_completion` re-sends a history that grows every iteration; input tokens grow quadratically

```python
  147          execute_tools: bool = True,
  148      ):
  149          active_agent = agent
  150          context_variables = copy.deepcopy(context_variables)
  151          history = copy.deepcopy(messages)
  152          init_len = len(messages)
  153  
  154          while len(history) - init_len < max_turns:
  155  
  156              message = {
  157                  "content": "",
  158                  "sender": agent.name,
  159                  "role": "assistant",
  160                  "function_call": None,
  161                  "tool_calls": defaultdict(
  162                      lambda: {
  163                          "function": {"arguments": "", "name": ""},
  164                          "id": "",
  165                          "type": "",
  166                      }
  167                  ),
  168              }
  169  
  170              # get completion with current history, agent
  171>             completion = self.get_chat_completion(
  172                  agent=active_agent,
  173                  history=history,
  174                  context_variables=context_variables,
  175                  model_override=model_override,
  176                  stream=True,
  177                  debug=debug,
  178              )
  179  
```

## AG003 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:453

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L453

> LLM call (litellm) inside 2 nested loops (lines 413, 451); calls multiply

```python
  429          if not scrape_result.get("error"):
  430              api_scrape_info[current_url] = scrape_result
  431              intermediate_steps.append({"step": f"Scrape URL: {current_url}", "content": scrape_result})
  432          else:
  433              print(f"[WARN] Error in scrape_result for {current_url}: {scrape_result.get('error')}")
  434              intermediate_steps.append({"step": f"Scrape Error for URL: {current_url}", "content": scrape_result.get("error")})
  435              continue  # Skip to the next URL
  436  
  437          # Step 6: Use LLM to extract relevant info and decide if more info is needed
  438          extraction_prompt = f"""The user wants to create a function described as follows: {description}.
  439  You have accumulated the following relevant API information so far:
  440  {accumulated_info}
  441  
  442  You have just scraped the following new API documentation:
  443  {json.dumps(scrape_result)}
  444  
  445  Based on the new information, extract any additional relevant API methods, endpoints, and usage patterns needed to implement the user's function. Indicate whether more information is required by setting 'requires_more_info' to true or false. If any other URLs should be scraped for further information, include them in the 'additional_urls' field."""
  446  
  447          # Chunk the extraction prompt if it's too long
  448          extraction_prompt_chunks = chunk_text(extraction_prompt)
  449          extraction_results = []
  450  
  451          for chunk in extraction_prompt_chunks:
  452              try:
  453>                 extraction_response = completion(
  454                      model="gpt-4o-mini",
  455                      messages=[
  456                          {"role": "system", "content": system_prompt},
  457                          {"role": "user", "content": chunk}
  458                      ],
  459                      response_format=ExtractionInfo
  460                  )
  461                  print(f"[DEBUG] Extraction Response: {extraction_response}")
```

## AG003 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:467

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L467

> call to `_translate_doc` inside 2 nested loops (lines 397, 461); calls multiply

```python
  443                      diff,
  444                      client,
  445                  )
  446  
  447              if not content:
  448                  console.print("  [yellow]⚠[/yellow] Empty response, skipping update")
  449                  continue
  450  
  451              if dry_run:
  452                  console.print(f"  [dim][DRY RUN] Would update {en_path}[/dim]")
  453              else:
  454                  en_path.write_text(content)
  455                  console.print(f"  [green]✓[/green] Updated {en_path}")
  456  
  457          if not content:
  458              continue
  459  
  460          resolved_edge = edge_root.resolve()
  461          for lang in _TRANSLATION_LANGS:
  462              lang_path = (edge_root / lang / rel_path).resolve()
  463              if not lang_path.is_relative_to(resolved_edge):
  464                  continue
  465  
  466              with console.status(f"  [cyan]Translating to {_LANGUAGE_NAMES[lang]}..."):
  467>                 translated = _translate_doc(content, lang, client)
  468  
  469              if dry_run:
  470                  console.print(f"  [dim][DRY RUN] Would write {lang_path}[/dim]")
  471              else:
  472                  lang_path.parent.mkdir(parents=True, exist_ok=True)
  473                  lang_path.write_text(translated)
  474                  console.print(f"  [green]✓[/green] Translated → {lang_path}")
  475  
```

## AG004 SWE-agent/SWE-agent sweagent/agent/models.py:835

https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/agent/models.py#L835

> call to `LiteLLMModel._query` runs once per item of a collection

```python
  811              wait=wait_random_exponential(min=self.config.retry.min_wait, max=self.config.retry.max_wait),
  812              reraise=True,
  813              retry=retry_if_not_exception_type(
  814                  (
  815                      ContextWindowExceededError,
  816                      CostLimitExceededError,
  817                      RuntimeError,
  818                      litellm.exceptions.UnsupportedParamsError,
  819                      litellm.exceptions.NotFoundError,
  820                      litellm.exceptions.PermissionDeniedError,
  821                      litellm.exceptions.ContextWindowExceededError,
  822                      litellm.exceptions.APIError,
  823                      litellm.exceptions.ContentPolicyViolationError,
  824                      TypeError,
  825                      litellm.exceptions.AuthenticationError,
  826                      ContentPolicyViolationError,
  827                      ModelConfigurationError,
  828                      KeyboardInterrupt,
  829                      IndexError,
  830                  )
  831              ),
  832              before_sleep=retry_warning,
  833          ):
  834              with attempt:
  835>                 result = self._query(messages, n=n, temperature=temperature)
  836          if n is None or n == 1:
  837              return result[0]
  838          return result
  839  
  840      def _history_to_messages(
  841          self,
  842          history: History,
  843      ) -> list[dict[str, str]]:
```

## AG004 openai/swarm examples/customer_service_streaming/src/swarm/engines/local_engine.py:304

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/src/swarm/engines/local_engine.py#L304

> call to `get_completion` runs once per item of a collection

```python
  280                          print(f"{Colors.RED}{message}{Colors.ENDC}")
  281                      #log
  282                      assistant.add_assistant_message(message)
  283                  else:
  284                      message = "Error evaluating output"
  285                      print(f"{Colors.RED}{message}{Colors.ENDC}")
  286                      assistant.add_assistant_message(message)
  287  
  288              return original_plan, plan_log
  289  
  290  
  291      def run_tests(self):
  292          total_groundtruth = 0
  293          total_planning = 0
  294          total_assistant = 0
  295          groundtruth_pass = 0
  296          planning_pass = 0
  297          assistant_pass = 0
  298          for task in self.tasks:
  299              original_plan, plan_log = self.run_task(task, test_mode=True)
  300  
  301              if task.groundtruth:
  302                  total_groundtruth += 1
  303                  # Assuming get_completion returns a response object with a content attribute
  304>                 response = get_completion(self.client, [{"role": "user", "content": EVAL_GROUNDTRUTH_PROMPT.format(original_plan, task.groundtruth)}])
  305                  if response.content.lower() == 'true':
  306                      groundtruth_pass += 1
  307                      print(f"{Colors.OKGREEN}✔ Groundtruth test passed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
  308                  else:
  309                      print(f"{Colors.RED}✘ Test failed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
  310  
  311                  total_assistant += 1
  312                  if task.assistant == task.expected_assistant:
```

## AG004 crewAIInc/crewAI lib/devtools/src/crewai_devtools/cli.py:1153

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/cli.py#L1153

> call to `translate_release_notes` runs once per item of a collection

```python
 1129                  f"{snapshot_path.relative_to(cwd)} and update docs.json + redirects"
 1130              )
 1131          else:
 1132              console.print(
 1133                  "[dim][DRY RUN][/dim] Skipping snapshot freeze (pre-release stays on Edge)"
 1134              )
 1135          prefix = "" if is_prerelease else "[docs-freeze] "
 1136          console.print(
 1137              f"[dim][DRY RUN][/dim] Would create branch docs/freeze-v{version}, "
 1138              f"open PR titled '{prefix}docs: snapshot and changelog for v{version}', "
 1139              "and wait for merge"
 1140          )
 1141          return None
 1142  
 1143      docs_paths_staged: list[str] = []
 1144  
 1145      # Step 1: update Edge changelogs first so the snapshot we freeze afterwards
 1146      # contains the new release's entry.
 1147      for lang in changelog_langs:
 1148          cl_path = edge_root / lang / "changelog.mdx"
 1149          if lang == "en":
 1150              notes_for_lang = release_notes
 1151          else:
 1152              console.print(f"[dim]Translating release notes to {lang}...[/dim]")
 1153>             notes_for_lang = translate_release_notes(release_notes, lang, openai_client)
 1154          if update_changelog(cl_path, version, notes_for_lang, lang=lang):
 1155              console.print(f"[green]✓[/green] Updated {cl_path.relative_to(cwd)}")
 1156              docs_paths_staged.append(str(cl_path))
 1157          else:
 1158              console.print(
 1159                  f"[yellow]Warning:[/yellow] Changelog not found at "
 1160                  f"{cl_path.relative_to(cwd)}"
 1161              )
```

## AG004 openai/swarm examples/customer_service_streaming/src/swarm/engines/local_engine.py:373

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/src/swarm/engines/local_engine.py#L373

> call to `LocalEngine.run_task` runs once per item of a collection

```python
  349          if total_assistant > 0:
  350              print(f"{Colors.OKGREEN}Passed {assistant_pass} assistant tests out of {total_assistant} tests. Success rate: {assistant_pass / total_assistant * 100}%{Colors.ENDC}\n")
  351          print("Completed testing the swarm\n\n")
  352  
  353      def deploy(self, client, test_mode=False, test_file_path=None):
  354          """
  355          Processes all tasks in the order they are listed in self.tasks.
  356          """
  357          self.client = client
  358          if test_mode and test_file_path:
  359              print("\nTesting the swarm\n\n")
  360              self.load_test_tasks(test_file_path)
  361              self.initialize_and_display_assistants()
  362              self.run_tests()
  363              for assistant in self.assistants:
  364                  if assistant.name == 'user_interface':
  365                      assistant.save_conversation(test=True)
  366          else:
  367              print("\n🐝🐝🐝 Deploying the swarm 🐝🐝🐝\n\n")
  368              self.initialize_and_display_assistants()
  369              print("\n" + "-" * 100 + "\n")
  370              for task in self.tasks:
  371                  print('Task',task.id)
  372                  print(f"{Colors.BOLD}Running task{Colors.ENDC}")
  373>                 self.run_task(task, test_mode)
  374                  print("\n" + "-" * 100 + "\n")
  375              #save the session
  376              for assistant in self.assistants:
  377                  if assistant.name == 'user_interface':
  378                      assistant.save_conversation()
  379               #assistant.print_conversation()
  380  
  381      def load_test_tasks(self, test_file_paths):
```

## AG004 openai/openai-agents-python docs/scripts/translate_docs.py:665

https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/docs/scripts/translate_docs.py#L665

> call to `translate_chunk` runs once per item of a collection

```python
  641          if (
  642              ENABLE_SMALL_CHUNK_TRANSLATION is True
  643              and len(current_chunk) >= 120  # required for gpt-4.5
  644              and line.startswith("#")
  645          ):
  646              chunks.append("\n".join(current_chunk))
  647              current_chunk = []
  648          current_chunk.append(line)
  649      if current_chunk:
  650          chunks.append("\n".join(current_chunk))
  651  
  652      inline_codes: list[str] = []
  653      protected_chunks: list[str] = []
  654      for chunk in chunks:
  655          protected_chunk, chunk_inline_codes = protect_inline_code(
  656              chunk, namespace=namespace, start_index=len(inline_codes)
  657          )
  658          protected_chunks.append(protected_chunk)
  659          inline_codes.extend(chunk_inline_codes)
  660      chunks = protected_chunks
  661  
  662      instructions = built_instructions(languages[lang_code], lang_code)
  663      translated_text = ""
  664      for _attempt in range(3):
  665>         translated_text = "\n".join(translate_chunk(chunk, instructions) for chunk in chunks)
  666          placeholders = [
  667              *(code_block_placeholder(namespace, idx) for idx in range(len(code_blocks))),
  668              *(inline_code_placeholder(namespace, idx) for idx in range(len(inline_codes))),
  669          ]
  670          if not placeholders_preserved(translated_text, placeholders):
  671              continue
  672          translated_text = restore_inline_code(translated_text, inline_codes, namespace=namespace)
  673          translated_text = restore_code_blocks(translated_text, code_blocks, namespace=namespace)
```

## AG004 openai/swarm examples/customer_service_streaming/src/swarm/engines/local_engine.py:322

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/src/swarm/engines/local_engine.py#L322

> call to `get_completion` runs once per item of a collection

```python
  298          for task in self.tasks:
  299              original_plan, plan_log = self.run_task(task, test_mode=True)
  300  
  301              if task.groundtruth:
  302                  total_groundtruth += 1
  303                  # Assuming get_completion returns a response object with a content attribute
  304                  response = get_completion(self.client, [{"role": "user", "content": EVAL_GROUNDTRUTH_PROMPT.format(original_plan, task.groundtruth)}])
  305                  if response.content.lower() == 'true':
  306                      groundtruth_pass += 1
  307                      print(f"{Colors.OKGREEN}✔ Groundtruth test passed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
  308                  else:
  309                      print(f"{Colors.RED}✘ Test failed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
  310  
  311                  total_assistant += 1
  312                  if task.assistant == task.expected_assistant:
  313                      assistant_pass += 1
  314                      print(f"{Colors.OKGREEN}✔ Correct assistant assigned. {Colors.ENDC}{Colors.OKBLUE} Expected: {Colors.ENDC}{task.expected_assistant}{Colors.OKBLUE}, Got: {Colors.ENDC}{task.assistant}{Colors.ENDC}\n")
  315                  else:
  316                      print(f"{Colors.RED}✘ Incorrect assistant assigned. {Colors.ENDC}{Colors.OKBLUE} Expected: {Colors.ENDC}{task.expected_assistant}{Colors.OKBLUE}, Got: {Colors.ENDC}{task.assistant}{Colors.ENDC}\n")
  317  
  318  
  319              elif task.expected_plan:
  320                  total_planning += 1
  321                  # Assuming get_completion returns a response object with a content attribute
  322>                 response = get_completion(self.client, [{"role": "user", "content": EVAL_PLANNING_PROMPT.format(original_plan, task.expected_plan)}])
  323  
  324                  if response.content.lower() == 'true':
  325                      planning_pass += 1
  326                      print(f"{Colors.OKGREEN}✔ Planning test passed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.expected_plan}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
  327                  else:
  328                      print(f"{Colors.RED}✘ Test failed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.expected_plan}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
  329  
  330                  total_assistant += 1
```

## AG004 openai/swarm examples/customer_service_streaming/src/swarm/engines/assistants_engine.py:323

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/src/swarm/engines/assistants_engine.py#L323

> call to `get_completion` runs once per item of a collection

```python
  299              return self.run_request(task.description, assistant,test_mode)
  300  
  301      def deploy(self, client,test_mode=False,test_file_path=None):
  302          """
  303          Processes all tasks in the order they are listed in self.tasks.
  304          """
  305          #Initialize swarm first
  306          self.client = client
  307          if test_mode and test_file_path:
  308              print("\nTesting the swarm\n\n")
  309              self.load_test_tasks(test_file_path)
  310          else:
  311              print("\n🐝🐝🐝 Deploying the swarm 🐝🐝🐝\n\n")
  312  
  313          self.initialize_and_display_assistants()
  314          total_tests = 0
  315          groundtruth_tests = 0
  316          assistant_tests = 0
  317          for task in self.tasks:
  318              output = self.run_task(task,test_mode)
  319  
  320              if test_mode and hasattr(task, 'groundtruth'):
  321                  total_tests += 1
  322  
  323>                 response = get_completion(self.client,[{"role":"user","content":EVALUATE_TASK_PROMPT.format(output,task.groundtruth)}])
  324  
  325                  if response.content=='True':
  326                      groundtruth_tests += 1
  327                      print(f"{Colors.OKGREEN}✔ Groundtruth test passed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{output}{Colors.ENDC}")
  328                  else:
  329                      print(f"{Colors.RED}✘ Test failed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{output}{Colors.ENDC}")
  330  
  331                  if task.assistant==task.expected_assistant:
```

## AG004 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:817

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L817

> call to `handle_api_documentation` runs once per item of a collection

```python
  793  
  794      # Reconstruct APIResponse objects from dicts
  795      from typing import Optional, List
  796      from pydantic import BaseModel
  797  
  798      class Endpoint(BaseModel):
  799          method: Optional[str]
  800          url: str
  801          description: Optional[str] = None
  802  
  803      class APIResponse(BaseModel):
  804          name: str
  805          purpose: str
  806          endpoints: List[Endpoint]
  807  
  808      external_apis = []
  809      for api_dict in external_apis_dicts:
  810          api_response_parsed = APIResponse(**api_dict)
  811          external_apis.append(api_response_parsed)
  812  
  813      # Step 5: Handle API documentation and extract contexts
  814      api_contexts = []
  815      for api_response_parsed in external_apis:
  816          api_name = api_response_parsed.name
  817>         result = handle_api_documentation(api_name, description, intermediate_steps)
  818          if "error" in result:
  819              return {"intermediate_steps": result["intermediate_steps"], "final_code": result["error"], "added_to_database": False}
  820          intermediate_steps = result["intermediate_steps"]
  821          api_contexts.extend(result["api_contexts"])
  822  
  823      # Step 6: Generate final function code
  824      result = generate_final_function_code(description, reusable_function_code, reference_function_code, api_contexts, intermediate_steps)
  825      if "error" in result:
```

## AG004 openai/openai-agents-python docs/scripts/translate_docs.py:759

https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/docs/scripts/translate_docs.py#L759

> call to `translate_file` runs once per item of a collection

```python
  735          print(f"Refreshing heading anchors in {target_path}")
  736          with open(target_path, "w", encoding="utf-8", newline="") as f:
  737              f.write(updated_text)
  738  
  739  
  740  def translate_single_source_file(
  741      file_path: str, *, check_translation_outdated: bool = True
  742  ) -> None:
  743      relative_path = os.path.relpath(file_path, source_dir)
  744      if "ref/" in relative_path.replace("\\", "/") or not file_path.endswith(".md"):
  745          return
  746      if check_translation_outdated and not should_translate_based_on_translation(file_path):
  747          print(f"Skipping {file_path}: The translated one is up-to-date.")
  748          refresh_heading_anchors(file_path, relative_path)
  749          return
  750  
  751      for lang_code in languages:
  752          target_dir = os.path.join(source_dir, lang_code)
  753          target_path = os.path.join(target_dir, relative_path)
  754  
  755          # Ensure the target directory exists
  756          os.makedirs(os.path.dirname(target_path), exist_ok=True)
  757  
  758          # Translate and save the file
  759>         translate_file(file_path, target_path, lang_code)
  760  
  761  
  762  def normalize_source_file_arg(file_arg: str) -> str:
  763      if file_arg.startswith(f"{source_dir}/"):
  764          return file_arg[len(source_dir) + 1 :]
  765      if os.path.isabs(file_arg):
  766          return os.path.relpath(file_arg, source_dir)
  767      return file_arg
```

## AG004 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:439

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L439

> call to `_update_doc` runs once per item of a collection

```python
  415              with console.status(f"  [cyan]Generating {rel_path}..."):
  416                  ref_content = None
  417                  parent = en_path.parent
  418                  if parent.exists():
  419                      siblings = list(parent.glob("*.mdx"))
  420                      if siblings:
  421                          ref_content = siblings[0].read_text()
  422                  content = _generate_doc(action_item.reason, ref_content, diff, client)
  423  
  424              if dry_run:
  425                  console.print(f"  [dim][DRY RUN] Would create {en_path}[/dim]")
  426                  console.print(f"  [dim]Preview: {content[:200]}...[/dim]")
  427              else:
  428                  en_path.parent.mkdir(parents=True, exist_ok=True)
  429                  en_path.write_text(content)
  430                  console.print(f"  [green]✓[/green] Created {en_path}")
  431  
  432          elif action_item.action == "update":
  433              if not en_path.exists():
  434                  console.print("  [yellow]⚠[/yellow] File not found, skipping update")
  435                  continue
  436  
  437              existing = en_path.read_text()
  438              with console.status(f"  [cyan]Updating {rel_path}..."):
  439>                 content = _update_doc(
  440                      action_item.reason,
  441                      action_item.section or "",
  442                      existing,
  443                      diff,
  444                      client,
  445                  )
  446  
  447              if not content:
```

## AG004 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:422

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L422

> call to `_generate_doc` runs once per item of a collection

```python
  398          if action_item.action not in ("create", "update") or not action_item.file:
  399              continue
  400  
  401          rel_path = action_item.file
  402          en_path = (edge_root / "en" / rel_path).resolve()
  403          if not en_path.is_relative_to(edge_root.resolve()):
  404              console.print(f"  [red]✗ Skipping unsafe path: {rel_path!r}[/red]")
  405              continue
  406          console.print(f"\n[bold]Processing:[/bold] {rel_path}")
  407  
  408          content: str = ""
  409  
  410          if action_item.action == "create":
  411              if en_path.exists():
  412                  console.print("  [yellow]⚠[/yellow] Already exists, skipping create")
  413                  continue
  414  
  415              with console.status(f"  [cyan]Generating {rel_path}..."):
  416                  ref_content = None
  417                  parent = en_path.parent
  418                  if parent.exists():
  419                      siblings = list(parent.glob("*.mdx"))
  420                      if siblings:
  421                          ref_content = siblings[0].read_text()
  422>                 content = _generate_doc(action_item.reason, ref_content, diff, client)
  423  
  424              if dry_run:
  425                  console.print(f"  [dim][DRY RUN] Would create {en_path}[/dim]")
  426                  console.print(f"  [dim]Preview: {content[:200]}...[/dim]")
  427              else:
  428                  en_path.parent.mkdir(parents=True, exist_ok=True)
  429                  en_path.write_text(content)
  430                  console.print(f"  [green]✓[/green] Created {en_path}")
```

## AG004 openai/swarm examples/customer_service_streaming/src/swarm/engines/assistants_engine.py:318

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/src/swarm/engines/assistants_engine.py#L318

> call to `AssistantsEngine.run_task` runs once per item of a collection

```python
  294                      print(f"No suitable assistant found for the task: {task.description}")
  295                  return None
  296  
  297              # Run the request with the determined or specified assistant
  298              self.reset_thread()
  299              return self.run_request(task.description, assistant,test_mode)
  300  
  301      def deploy(self, client,test_mode=False,test_file_path=None):
  302          """
  303          Processes all tasks in the order they are listed in self.tasks.
  304          """
  305          #Initialize swarm first
  306          self.client = client
  307          if test_mode and test_file_path:
  308              print("\nTesting the swarm\n\n")
  309              self.load_test_tasks(test_file_path)
  310          else:
  311              print("\n🐝🐝🐝 Deploying the swarm 🐝🐝🐝\n\n")
  312  
  313          self.initialize_and_display_assistants()
  314          total_tests = 0
  315          groundtruth_tests = 0
  316          assistant_tests = 0
  317          for task in self.tasks:
  318>             output = self.run_task(task,test_mode)
  319  
  320              if test_mode and hasattr(task, 'groundtruth'):
  321                  total_tests += 1
  322  
  323                  response = get_completion(self.client,[{"role":"user","content":EVALUATE_TASK_PROMPT.format(output,task.groundtruth)}])
  324  
  325                  if response.content=='True':
  326                      groundtruth_tests += 1
```

## AG004 openai/swarm examples/customer_service_streaming/src/swarm/engines/local_engine.py:299

https://github.com/openai/swarm/blob/6af0b4caf37dca4526dfd98e9fbd8ce36e7eeb22/examples/customer_service_streaming/src/swarm/engines/local_engine.py#L299

> call to `LocalEngine.run_task` runs once per item of a collection

```python
  275                       success_flag = False if output[0].lower() == 'false' else bool(output[0])
  276                      message = output[1]
  277                      if success_flag:
  278                          print(f'\n\033[93m{message}\033[0m')
  279                      else:
  280                          print(f"{Colors.RED}{message}{Colors.ENDC}")
  281                      #log
  282                      assistant.add_assistant_message(message)
  283                  else:
  284                      message = "Error evaluating output"
  285                      print(f"{Colors.RED}{message}{Colors.ENDC}")
  286                      assistant.add_assistant_message(message)
  287  
  288              return original_plan, plan_log
  289  
  290  
  291      def run_tests(self):
  292          total_groundtruth = 0
  293          total_planning = 0
  294          total_assistant = 0
  295          groundtruth_pass = 0
  296          planning_pass = 0
  297          assistant_pass = 0
  298          for task in self.tasks:
  299>             original_plan, plan_log = self.run_task(task, test_mode=True)
  300  
  301              if task.groundtruth:
  302                  total_groundtruth += 1
  303                  # Assuming get_completion returns a response object with a content attribute
  304                  response = get_completion(self.client, [{"role": "user", "content": EVAL_GROUNDTRUTH_PROMPT.format(original_plan, task.groundtruth)}])
  305                  if response.content.lower() == 'true':
  306                      groundtruth_pass += 1
  307                      print(f"{Colors.OKGREEN}✔ Groundtruth test passed for: {Colors.ENDC}{task.description}{Colors.OKBLUE}. Expected: {Colors.ENDC}{task.groundtruth}{Colors.OKBLUE}, Got: {Colors.ENDC}{original_plan}{Colors.ENDC}")
```

## AG004 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:620

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L620

> LLM call (litellm) runs once per item of a collection

```python
  596      You have the following internal reference functions:
  597      {json.dumps(reference_function_code)}
  598  
  599      You have the following context on the necessary external APIs and their usage:
  600      {json.dumps(api_contexts)}
  601  
  602      Generate a complete function using the functionz framework that adheres to the provided guidelines and utilizes the specified internal and external functions. Ensure the function is registered with the correct metadata, dependencies, and includes all relevant imports.
  603  
  604      Provide the function details in a structured format including:
  605      1. Function name
  606      2. Complete function code (do not the @babyagi.register_function decorator)
  607      3. Metadata (description)
  608      4. Imports
  609      5. Dependencies
  610      6. Key dependencies
  611      7. Triggers (if any)
  612      """
  613  
  614      # Chunk the final prompt if it's too long
  615      final_prompt_chunks = chunk_text(final_prompt)
  616      final_results = []
  617  
  618      for chunk in final_prompt_chunks:
  619          try:
  620>             final_response = completion(
  621                  model="gpt-4o-mini",
  622                  messages=[
  623                      {"role": "system", "content": system_prompt},
  624                      {"role": "user", "content": chunk}
  625                  ],
  626                  response_format=GeneratedFunction
  627              )
  628              print(f"[DEBUG] Final Response: {final_response}")
```

## AG005 crewAIInc/crewAI lib/crewai/src/crewai/llm.py:1949

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/crewai/src/crewai/llm.py#L1949

> `acall` makes LLM calls and calls itself, with no depth parameter to stop it

```python
 1925  
 1926                          logging.info("Retrying LLM call without the unsupported 'stop'")
 1927  
 1928                          return self.call(
 1929                              messages,
 1930                              tools=tools,
 1931                              callbacks=callbacks,
 1932                              available_functions=available_functions,
 1933                              from_task=from_task,
 1934                              from_agent=from_agent,
 1935                              response_model=response_model,
 1936                          )
 1937  
 1938                      crewai_event_bus.emit(
 1939                          self,
 1940                          event=LLMCallFailedEvent(
 1941                              error=str(e),
 1942                              from_task=from_task,
 1943                              from_agent=from_agent,
 1944                              call_id=get_current_call_id(),
 1945                          ),
 1946                      )
 1947                      raise
 1948  
 1949>     async def acall(
 1950          self,
 1951          messages: str | list[LLMMessage],
 1952          tools: list[dict[str, BaseTool]] | None = None,
 1953          callbacks: list[Any] | None = None,
 1954          available_functions: dict[str, Any] | None = None,
 1955          from_task: Task | None = None,
 1956          from_agent: BaseAgent | None = None,
 1957          response_model: type[BaseModel] | None = None,
```

## AG005 crewAIInc/crewAI lib/crewai/src/crewai/llm.py:1807

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/crewai/src/crewai/llm.py#L1807

> `call` makes LLM calls and calls itself, with no depth parameter to stop it

```python
 1783              except Exception as e:
 1784                  fn = available_functions.get(function_name, lambda: None)
 1785                  logging.error(f"Error executing function '{function_name}': {e}")
 1786                  crewai_event_bus.emit(
 1787                      self,
 1788                      event=LLMCallFailedEvent(
 1789                          error=f"Tool execution error: {e!s}",
 1790                          from_task=from_task,
 1791                          from_agent=from_agent,
 1792                          call_id=get_current_call_id(),
 1793                      ),
 1794                  )
 1795                  crewai_event_bus.emit(
 1796                      self,
 1797                      event=ToolUsageErrorEvent(
 1798                          tool_name=function_name,
 1799                          tool_args=function_args,
 1800                          error=f"Tool execution error: {e!s}",
 1801                          from_task=from_task,
 1802                          from_agent=from_agent,
 1803                      ),
 1804                  )
 1805          return None
 1806  
 1807>     def call(
 1808          self,
 1809          messages: str | list[LLMMessage],
 1810          tools: list[dict[str, BaseTool]] | None = None,
 1811          callbacks: list[Any] | None = None,
 1812          available_functions: dict[str, Any] | None = None,
 1813          from_task: Task | None = None,
 1814          from_agent: BaseAgent | None = None,
 1815          response_model: type[BaseModel] | None = None,
```

## AG006 openai/openai-agents-python docs/scripts/translate_docs.py:612

https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/docs/scripts/translate_docs.py#L612

> LLM call (openai.responses) sets no output-token cap

```python
  588  def restore_code_blocks(markdown: str, code_blocks: list[str], *, namespace: str) -> str:
  589      replacements = {
  590          code_block_placeholder(namespace, idx): code_block
  591          for idx, code_block in enumerate(code_blocks)
  592      }
  593      return restore_placeholders(markdown, replacements)
  594  
  595  
  596  def translate_chunk(chunk: str, instructions: str) -> str:
  597      if OPENAI_MODEL.startswith("gpt-5"):
  598          response = openai_client.responses.create(
  599              model=OPENAI_MODEL,
  600              instructions=instructions,
  601              input=chunk,
  602              reasoning={"effort": "high"},
  603              text={"verbosity": "medium"},
  604          )
  605      elif OPENAI_MODEL.startswith("o"):
  606          response = openai_client.responses.create(
  607              model=OPENAI_MODEL,
  608              instructions=instructions,
  609              input=chunk,
  610          )
  611      else:
  612>         response = openai_client.responses.create(
  613              model=OPENAI_MODEL,
  614              instructions=instructions,
  615              input=chunk,
  616              temperature=0.0,
  617          )
  618      return response.output_text
  619  
  620  
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/self_build2.py:76

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/self_build2.py#L76

> LLM call (litellm) sets no output-token cap

```python
   52  
   53  {
   54      "queries": [
   55          "First synthetic query.",
   56          "Second synthetic query.",
   57          ...
   58      ]
   59  }
   60  
   61  Provide only the JSON response, without any additional text.
   62  """
   63  
   64      class QueryGenerationResponse(BaseModel):
   65          queries: List[str] = Field(..., description="A list of generated synthetic queries.")
   66  
   67      generation_prompt = f"""
   68  User Description:
   69  \"\"\"{user_description}\"\"\"
   70  
   71  Number of Queries to Generate:
   72  {num_queries}
   73  """
   74  
   75      try:
   76>         generation_response = completion(
   77              model="gpt-4o-mini",
   78              messages=[
   79                  {"role": "system", "content": system_prompt},
   80                  {"role": "user", "content": generation_prompt}
   81              ],
   82              response_format=QueryGenerationResponse
   83          )
   84          print(f"[DEBUG] Generation Response: {generation_response}")
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/choose_or_create_function.py:76

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/choose_or_create_function.py#L76

> LLM call (litellm) sets no output-token cap

```python
   52  
   53  {
   54      "use_existing_function": true or false,
   55      "function_name": "name of the existing function" (if applicable),
   56      "function_description": "description of the function to generate" (if applicable)
   57  }
   58  
   59  Provide only the JSON response, without any additional text.
   60  """
   61  
   62      class FunctionDecision(BaseModel):
   63          use_existing_function: bool = Field(..., description="True if an existing function can be used; False if a new function needs to be generated.")
   64          function_name: Optional[str] = Field(None, description="Name of the existing function to use.")
   65          function_description: Optional[str] = Field(None, description="Description of the new function to generate.")
   66  
   67      decision_prompt = f"""
   68  The user has provided the following input:
   69  \"{user_input}\"
   70  
   71  Available Functions:
   72  {existing_functions}
   73  """
   74  
   75      try:
   76>         decision_response = completion(
   77              model="gpt-4o-mini",
   78              messages=[
   79                  {"role": "system", "content": system_prompt},
   80                  {"role": "user", "content": decision_prompt}
   81              ],
   82              response_format=FunctionDecision
   83          )
   84          print(f"[DEBUG] Decision Response: {decision_response}")
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:377

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L377

> LLM call (litellm) sets no output-token cap

```python
  353                  last_newline = text.rfind('\n', end - overlap, end)
  354                  if last_newline != -1:
  355                      end = last_newline + 1
  356              chunks.append(text[start:end])
  357              start = end - overlap
  358          return chunks
  359  
  360      search_query = f"{api_name} API documentation python"
  361      print(f"[DEBUG] Searching for API documentation with query: {search_query}")
  362      try:
  363          search_results = serpapi_search_v2(query=search_query)
  364          print(f"[DEBUG] Search Results for {api_name}: {search_results}")
  365          intermediate_steps.append({"step": f"Search API Documentation for {api_name}", "content": search_results})
  366      except Exception as e:
  367          print(f"[ERROR] serpapi_search_v2 failed for {api_name}: {e}")
  368          intermediate_steps.append({"step": f"Error Searching API Documentation for {api_name}", "content": str(e)})
  369          return {"intermediate_steps": intermediate_steps, "error": "# Error searching API documentation."}
  370  
  371      link_selection_prompt = f"""You are given the following search results for the query "{search_query}":
  372      {json.dumps(search_results)}
  373  
  374      Which links seem most relevant for obtaining Python API documentation? Return them as a structured JSON list of URLs."""
  375  
  376      try:
  377>         link_selection_response = completion(
  378              model="gpt-4o-mini",
  379              messages=[
  380                  {"role": "system", "content": system_prompt},
  381                  {"role": "user", "content": link_selection_prompt}
  382              ],
  383              response_format=URLSelection
  384          )
  385          print(f"[DEBUG] Link Selection Response for {api_name}: {link_selection_response}")
```

## AG006 crewAIInc/crewAI lib/crewai-tools/src/crewai_tools/tools/ai_mind_tool/ai_mind_tool.py:93

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/crewai-tools/src/crewai_tools/tools/ai_mind_tool/ai_mind_tool.py#L93

> LLM call (openai.chat) sets no output-token cap

```python
   69                  engine=datasource["engine"],
   70                  description=datasource["description"],
   71                  connection_data=datasource["connection_data"],
   72                  tables=datasource["tables"],
   73              )
   74              datasources.append(config)
   75  
   76          name = f"{AIMindToolConstants.MIND_NAME_PREFIX}_{secrets.token_hex(5)}"
   77  
   78          mind = minds_client.minds.create(
   79              name=name, datasources=datasources, replace=True
   80          )
   81  
   82          self.mind_name = mind.name
   83  
   84      def _run(self, query: str) -> str | None:
   85          # The Minds API is OpenAI compatible and therefore, the OpenAI client can be used.
   86          openai_client = OpenAI(
   87              base_url=AIMindToolConstants.MINDS_API_BASE_URL, api_key=self.api_key
   88          )
   89  
   90          if self.mind_name is None:
   91              raise ValueError("Mind name is not set.")
   92  
   93>         completion = openai_client.chat.completions.create(
   94              model=self.mind_name,
   95              messages=[{"role": "user", "content": query}],
   96              stream=False,
   97          )
   98          if not isinstance(completion, ChatCompletion):
   99              raise ValueError("Invalid response from AI-Mind")
  100  
  101          return completion.choices[0].message.content
```

## AG006 openai/openai-agents-python docs/scripts/translate_docs.py:598

https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/docs/scripts/translate_docs.py#L598

> LLM call (openai.responses) sets no output-token cap

```python
  574          inline_codes.append(markdown[start:end])
  575          cursor = end
  576      parts.append(markdown[cursor:])
  577      return "".join(parts), inline_codes
  578  
  579  
  580  def restore_inline_code(markdown: str, inline_codes: list[str], *, namespace: str = "") -> str:
  581      replacements = {
  582          inline_code_placeholder(namespace, idx): inline_code
  583          for idx, inline_code in enumerate(inline_codes)
  584      }
  585      return restore_placeholders(markdown, replacements)
  586  
  587  
  588  def restore_code_blocks(markdown: str, code_blocks: list[str], *, namespace: str) -> str:
  589      replacements = {
  590          code_block_placeholder(namespace, idx): code_block
  591          for idx, code_block in enumerate(code_blocks)
  592      }
  593      return restore_placeholders(markdown, replacements)
  594  
  595  
  596  def translate_chunk(chunk: str, instructions: str) -> str:
  597      if OPENAI_MODEL.startswith("gpt-5"):
  598>         response = openai_client.responses.create(
  599              model=OPENAI_MODEL,
  600              instructions=instructions,
  601              input=chunk,
  602              reasoning={"effort": "high"},
  603              text={"verbosity": "medium"},
  604          )
  605      elif OPENAI_MODEL.startswith("o"):
  606          response = openai_client.responses.create(
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:453

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L453

> LLM call (litellm) sets no output-token cap

```python
  429          if not scrape_result.get("error"):
  430              api_scrape_info[current_url] = scrape_result
  431              intermediate_steps.append({"step": f"Scrape URL: {current_url}", "content": scrape_result})
  432          else:
  433              print(f"[WARN] Error in scrape_result for {current_url}: {scrape_result.get('error')}")
  434              intermediate_steps.append({"step": f"Scrape Error for URL: {current_url}", "content": scrape_result.get("error")})
  435              continue  # Skip to the next URL
  436  
  437          # Step 6: Use LLM to extract relevant info and decide if more info is needed
  438          extraction_prompt = f"""The user wants to create a function described as follows: {description}.
  439  You have accumulated the following relevant API information so far:
  440  {accumulated_info}
  441  
  442  You have just scraped the following new API documentation:
  443  {json.dumps(scrape_result)}
  444  
  445  Based on the new information, extract any additional relevant API methods, endpoints, and usage patterns needed to implement the user's function. Indicate whether more information is required by setting 'requires_more_info' to true or false. If any other URLs should be scraped for further information, include them in the 'additional_urls' field."""
  446  
  447          # Chunk the extraction prompt if it's too long
  448          extraction_prompt_chunks = chunk_text(extraction_prompt)
  449          extraction_results = []
  450  
  451          for chunk in extraction_prompt_chunks:
  452              try:
  453>                 extraction_response = completion(
  454                      model="gpt-4o-mini",
  455                      messages=[
  456                          {"role": "system", "content": system_prompt},
  457                          {"role": "user", "content": chunk}
  458                      ],
  459                      response_format=ExtractionInfo
  460                  )
  461                  print(f"[DEBUG] Extraction Response: {extraction_response}")
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/choose_or_create_function.py:164

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/choose_or_create_function.py#L164

> LLM call (litellm) sets no output-token cap

```python
  140          intermediate_steps.append({"step": "Error Fetching Function Info", "content": str(e)})
  141          return {"intermediate_steps": intermediate_steps, "error": "# Error fetching function info."}
  142  
  143      # Step 4: Use LLM to generate parameters for the function based on user input
  144      param_prompt = f"""
  145      The user has provided the following input:
  146      \"{user_input}\"
  147  
  148      The function to execute is:
  149      {function_info.get('code', '')}
  150  
  151      Generate a JSON object with a single key "parameters" that contains the parameters required by the function, filled in appropriately based on the user's input.
  152  
  153      Return only the JSON object, with no additional text.
  154      """
  155  
  156      try:
  157          # Define a Pydantic model with a fixed field "parameters"
  158          class FunctionParameters(BaseModel):
  159              parameters: Dict[str, Any]
  160  
  161              class Config:
  162                  extra = 'forbid'  # This sets 'additionalProperties' to False
  163  
  164>         param_response = completion(
  165              model="gpt-4o-mini",
  166              messages=[
  167                  {"role": "system", "content": "You are an assistant that provides only JSON-formatted data, with no additional text."},
  168                  {"role": "user", "content": param_prompt}
  169              ],
  170              response_format=FunctionParameters  # Keep the same parsing format
  171          )
  172          print(f"[DEBUG] Parameter Response: {param_response}")
```

## AG006 huggingface/smolagents examples/open_deep_research/scripts/mdconvert.py:756

https://github.com/huggingface/smolagents/blob/96f33faaf028479119ec8d34507b47694cf14e34/examples/open_deep_research/scripts/mdconvert.py#L756

> LLM call (openai.chat) sets no output-token cap

```python
  732  
  733          data_uri = ""
  734          with open(local_path, "rb") as image_file:
  735              content_type, encoding = mimetypes.guess_type("_dummy" + extension)
  736              if content_type is None:
  737                  content_type = "image/jpeg"
  738              image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
  739              data_uri = f"data:{content_type};base64,{image_base64}"
  740  
  741          messages = [
  742              {
  743                  "role": "user",
  744                  "content": [
  745                      {"type": "text", "text": prompt},
  746                      {
  747                          "type": "image_url",
  748                          "image_url": {
  749                              "url": data_uri,
  750                          },
  751                      },
  752                  ],
  753              }
  754          ]
  755  
  756>         response = client.chat.completions.create(model=model, messages=messages)
  757          return response.choices[0].message.content
  758  
  759  
  760  class FileConversionException(Exception):
  761      pass
  762  
  763  
  764  class UnsupportedFormatException(Exception):
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:620

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L620

> LLM call (litellm) sets no output-token cap

```python
  596      You have the following internal reference functions:
  597      {json.dumps(reference_function_code)}
  598  
  599      You have the following context on the necessary external APIs and their usage:
  600      {json.dumps(api_contexts)}
  601  
  602      Generate a complete function using the functionz framework that adheres to the provided guidelines and utilizes the specified internal and external functions. Ensure the function is registered with the correct metadata, dependencies, and includes all relevant imports.
  603  
  604      Provide the function details in a structured format including:
  605      1. Function name
  606      2. Complete function code (do not the @babyagi.register_function decorator)
  607      3. Metadata (description)
  608      4. Imports
  609      5. Dependencies
  610      6. Key dependencies
  611      7. Triggers (if any)
  612      """
  613  
  614      # Chunk the final prompt if it's too long
  615      final_prompt_chunks = chunk_text(final_prompt)
  616      final_results = []
  617  
  618      for chunk in final_prompt_chunks:
  619          try:
  620>             final_response = completion(
  621                  model="gpt-4o-mini",
  622                  messages=[
  623                      {"role": "system", "content": system_prompt},
  624                      {"role": "user", "content": chunk}
  625                  ],
  626                  response_format=GeneratedFunction
  627              )
  628              print(f"[DEBUG] Final Response: {final_response}")
```

## AG006 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:265

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L265

> LLM call (openai.chat) sets no output-token cap

```python
  241      section: str,
  242      existing_content: str,
  243      diff_context: str,
  244      client: OpenAI,
  245  ) -> str:
  246      """Update an existing documentation page.
  247  
  248      Args:
  249          reason: Why this update is needed.
  250          section: Which section to update.
  251          existing_content: Current doc content.
  252          diff_context: Relevant portion of the diff.
  253          client: OpenAI client.
  254  
  255      Returns:
  256          Updated MDX content.
  257      """
  258      prompt = _UPDATE_DOC_PROMPT.format(
  259          reason=reason,
  260          section=section,
  261          existing_content=existing_content,
  262          diff_context=diff_context[:10000],
  263      )
  264  
  265>     response = client.chat.completions.create(
  266          model="gpt-4o",
  267          messages=[
  268              {
  269                  "role": "system",
  270                  "content": "You are a technical writer. Output only the complete updated MDX file.",
  271              },
  272              {"role": "user", "content": prompt},
  273          ],
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:101

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L101

> LLM call (litellm) sets no output-token cap

```python
   77  
   78      Metadata and Dependencies: When writing functions, you may include optional metadata (such as descriptions) and dependencies. Dependencies can be other functions or secrets (API keys, etc.).
   79  
   80      Import Handling: Manage imports by specifying them in the decorator as dictionaries with 'name' and 'lib' keys. Include these imports within the function body.
   81  
   82      Secret Management: When using API keys or authentication secrets, reference the stored key with globals()['key_name'].
   83  
   84      Error Handling: Functions should handle errors gracefully, catching exceptions if necessary.
   85  
   86      General Guidelines: Use simple, clean, and readable code. Follow the structure and syntax of the functionz framework. Ensure proper function documentation via metadata.
   87      """
   88  
   89      display_prompt = f"""You are an assistant helping a developer build a function using the functionz framework.
   90  
   91      The user has provided the following function description: {description}
   92  
   93      The current available functions are listed below. Please specify if any of these functions can be used directly (for reuse), or if any should be referenced while building the new function. Return your response as structured JSON.
   94  
   95      Available Functions:
   96      {existing_functions}
   97      """
   98  
   99      # Step 2.1: Make the LLM call using JSON mode with Pydantic model
  100      try:
  101>         display_response = completion(
  102              model="gpt-4o-mini",
  103              messages=[
  104                  {"role": "system", "content": system_prompt},
  105                  {"role": "user", "content": display_prompt}
  106              ],
  107              response_format=FunctionSuggestion
  108          )
  109          print(f"[DEBUG] Display Response: {display_response}")
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/drafts/generate_function.py:237

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/drafts/generate_function.py#L237

> LLM call (litellm) sets no output-token cap

```python
  213          @validator("endpoints", pre=True, each_item=True)
  214          def convert_to_endpoint(cls, v):
  215              """Convert string URLs into Endpoint objects if necessary."""
  216              if isinstance(v, str):
  217                  return Endpoint(url=v)  # Create an Endpoint object from a URL string
  218              return v
  219  
  220      class APIResponse(BaseModel):
  221          name: str
  222          purpose: str
  223          endpoints: List[Endpoint]
  224  
  225      # System prompt
  226      system_prompt = """
  227      [Your existing system prompt here]
  228      """
  229  
  230      prompt_for_apis = f"""You are an assistant analyzing function requirements.
  231  
  232      The user has provided the following function description: {description}.
  233  
  234      Identify if this function will require external APIs (including SDKs or libraries). If so, return a structured JSON with a list of external APIs, their purposes, and any relevant endpoints."""
  235  
  236      try:
  237>         api_response = completion(
  238              model="gpt-4o-mini",
  239              messages=[
  240                  {"role": "system", "content": system_prompt},
  241                  {"role": "user", "content": prompt_for_apis}
  242              ],
  243              response_format=APIDetails
  244          )
  245          print(f"[DEBUG] API Response: {api_response}")
```

## AG006 openai/openai-agents-python docs/scripts/translate_docs.py:606

https://github.com/openai/openai-agents-python/blob/125efa029b4bfd84238bd2c4fd69c3406f802663/docs/scripts/translate_docs.py#L606

> LLM call (openai.responses) sets no output-token cap

```python
  582          inline_code_placeholder(namespace, idx): inline_code
  583          for idx, inline_code in enumerate(inline_codes)
  584      }
  585      return restore_placeholders(markdown, replacements)
  586  
  587  
  588  def restore_code_blocks(markdown: str, code_blocks: list[str], *, namespace: str) -> str:
  589      replacements = {
  590          code_block_placeholder(namespace, idx): code_block
  591          for idx, code_block in enumerate(code_blocks)
  592      }
  593      return restore_placeholders(markdown, replacements)
  594  
  595  
  596  def translate_chunk(chunk: str, instructions: str) -> str:
  597      if OPENAI_MODEL.startswith("gpt-5"):
  598          response = openai_client.responses.create(
  599              model=OPENAI_MODEL,
  600              instructions=instructions,
  601              input=chunk,
  602              reasoning={"effort": "high"},
  603              text={"verbosity": "medium"},
  604          )
  605      elif OPENAI_MODEL.startswith("o"):
  606>         response = openai_client.responses.create(
  607              model=OPENAI_MODEL,
  608              instructions=instructions,
  609              input=chunk,
  610          )
  611      else:
  612          response = openai_client.responses.create(
  613              model=OPENAI_MODEL,
  614              instructions=instructions,
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/default/function_calling_chat.py:154

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/default/function_calling_chat.py#L154

> LLM call (litellm) sets no output-token cap

```python
  130          for tool_call in tool_calls:
  131              function_name = tool_call['function']['name']
  132              function_args = json.loads(tool_call['function']['arguments'])
  133              tool_call_id = tool_call['id']  # Extract the tool_call_id
  134  
  135              # Execute the function using execute_function_wrapper
  136              try:
  137                  function_response = execute_function_wrapper(function_name, **function_args)
  138              except Exception as e:
  139                  function_response = f"Error executing function '{function_name}': {str(e)}"
  140  
  141              # Ensure function_response is a string
  142              if not isinstance(function_response, str):
  143                  function_response = json.dumps(function_response)
  144  
  145              # Append the function response to the chat context
  146              chat_context.append({
  147                  "tool_call_id": tool_call_id,  # Include the tool_call_id
  148                  "role": "tool",  # Use 'tool' as per LiteLLM's protocol
  149                  "name": function_name,
  150                  "content": function_response
  151              })
  152  
  153          # Call LiteLLM again with the updated context including function responses
  154>         second_response = litellm.completion(
  155              model="gpt-4-turbo",
  156              messages=chat_context
  157          )
  158  
  159          # Extract and return the assistant's final response
  160          assistant_response = second_response['choices'][0]['message']['content']
  161          return assistant_response
  162      else:
```

## AG006 crewAIInc/crewAI lib/devtools/src/crewai_devtools/cli.py:1031

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/cli.py#L1031

> LLM call (openai.chat) sets no output-token cap

```python
 1007  
 1008          except subprocess.CalledProcessError:
 1009              commit_range, commits = get_commits_from_last_tag(
 1010                  tag_name, version, cwd=cwd
 1011              )
 1012  
 1013          github_contributors = get_github_contributors(
 1014              commit_range, repo=gh_repo, cwd=cwd
 1015          )
 1016  
 1017          if openai_client is None:
 1018              openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
 1019  
 1020          if commits.strip():
 1021              contributors_section = ""
 1022              if github_contributors:
 1023                  contributors_section = f"\n\n## Contributors\n\n{', '.join([f'@{u}' for u in github_contributors])}"
 1024  
 1025              prompt = RELEASE_NOTES_PROMPT.substitute(
 1026                  version=version,
 1027                  commits=commits,
 1028                  contributors_section=contributors_section,
 1029              )
 1030  
 1031>             response = openai_client.chat.completions.create(
 1032                  model="gpt-4o-mini",
 1033                  messages=[
 1034                      {
 1035                          "role": "system",
 1036                          "content": "You are a helpful assistant that generates clear, concise release notes.",
 1037                      },
 1038                      {"role": "user", "content": prompt},
 1039                  ],
```

## AG006 assafelovic/gpt-researcher evals/context_filter/judge.py:37

https://github.com/assafelovic/gpt-researcher/blob/3582a6841fe7dc801e2a34e34ee408641aea9bce/evals/context_filter/judge.py#L37

> LLM call (openai.chat) sets no output-token cap

```python
   13                strategy wins both orders.
   14  
   15      python -m evals.context_filter.judge --results results/ --judge-model gpt-5.4
   16      python -m evals.context_filter.judge --results results/ --baseline none --only jev jev_wide
   17  """
   18  
   19  import argparse
   20  import asyncio
   21  import json
   22  import re
   23  import statistics
   24  from collections import defaultdict
   25  from pathlib import Path
   26  
   27  from openai import AsyncOpenAI
   28  
   29  from evals.simple_evals.simpleqa_eval import GRADER_TEMPLATE
   30  
   31  client = AsyncOpenAI(max_retries=6, timeout=300)
   32  SEM = asyncio.Semaphore(8)
   33  
   34  
   35  async def ask(model: str, prompt: str) -> str:
   36      async with SEM:
   37>         response = await client.chat.completions.create(
   38              model=model, messages=[{"role": "user", "content": prompt}])
   39      return response.choices[0].message.content.strip()
   40  
   41  
   42  async def grade_simpleqa(model: str, r: dict) -> str:
   43      text = await ask(model, GRADER_TEMPLATE.format(
   44          question=r["query"], target=r["answer"], predicted_answer=r["report"] or "(no report)"))
   45      return {"A": "CORRECT", "B": "INCORRECT", "C": "NOT_ATTEMPTED"}.get(text[:1], "NOT_ATTEMPTED")
```

## AG006 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:180

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L180

> LLM call (openai.chat) sets no output-token cap

```python
  156      )
  157      return result.stdout.strip()
  158  
  159  
  160  def _get_diff(base: str) -> str:
  161      """Get the git diff against a base ref."""
  162      return _run_git(["diff", base, "--", "lib/"])
  163  
  164  
  165  def _get_openai_client() -> OpenAI:
  166      """Create an OpenAI client."""
  167      return OpenAI()
  168  
  169  
  170  def _analyze_diff(diff: str, client: OpenAI) -> DocsAnalysis:
  171      """Analyze a git diff and determine what docs are needed.
  172  
  173      Args:
  174          diff: Git diff output.
  175          client: OpenAI client.
  176  
  177      Returns:
  178          Structured analysis result with actions.
  179      """
  180>     response = client.beta.chat.completions.parse(
  181          model="gpt-4o-mini",
  182          messages=[
  183              {"role": "system", "content": _ANALYZE_SYSTEM},
  184              {"role": "user", "content": _ANALYZE_USER + diff[:50000]},
  185          ],
  186          temperature=0.2,
  187          response_format=DocsAnalysis,
  188      )
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/default/ai_functions.py:13

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/default/ai_functions.py#L13

> LLM call (litellm) sets no output-token cap

```python
    1  # packs/ai_generator.py
    2  
    3  from functionz.core.framework import func
    4  
    5  @func.register_function(
    6      metadata={"description": "GPT Call function using LiteLLm"},
    7      imports=["litellm"],
    8      key_dependencies=["openai_api_key"]
    9  )
   10  def gpt_call(prompt: str) -> str:
   11      from litellm import completion
   12      messages = [{"role": "user", "content": prompt}]
   13>     response = completion(model="gpt-4o", messages=messages)
   14      return response['choices'][0]['message']['content']
   15  
   16  @func.register_function(
   17      metadata={"description": "Generates a description for a function using LiteLLm"},
   18      dependencies=["gpt_call"]
   19  )
   20  def description_writer(function_code: str) -> str:
   21      prompt = (
```

## AG006 crewAIInc/crewAI lib/devtools/src/crewai_devtools/cli.py:515

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/cli.py#L515

> LLM call (openai.chat) sets no output-token cap

```python
  491      lang: ChangelogLang,
  492      client: OpenAI,
  493  ) -> str:
  494      """Translate release notes into the target language using OpenAI.
  495  
  496      Args:
  497          release_notes: English release notes markdown.
  498          lang: Language code (e.g., "pt-BR", "ko").
  499          client: OpenAI client instance.
  500  
  501      Returns:
  502          Translated release notes, or original on failure.
  503      """
  504      locale_cfg = _CHANGELOG_LOCALES.get(lang)
  505      if not locale_cfg:
  506          return release_notes
  507  
  508      language_name = locale_cfg["language_name"]
  509      prompt = TRANSLATE_RELEASE_NOTES_PROMPT.substitute(
  510          language=language_name,
  511          release_notes=release_notes,
  512      )
  513  
  514      try:
  515>         response = client.chat.completions.create(
  516              model="gpt-4o-mini",
  517              messages=[
  518                  {
  519                      "role": "system",
  520                      "content": f"You are a professional translator. Translate technical documentation into {language_name}.",
  521                  },
  522                  {"role": "user", "content": prompt},
  523              ],
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/default/function_calling_chat.py:112

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/default/function_calling_chat.py#L112

> LLM call (litellm) sets no output-token cap

```python
   88                          "properties": {},
   89                          "required": []
   90                      },
   91                  },
   92              }
   93  
   94              # Map input_parameters to the tool's parameters
   95              for param in function_data.get('input_parameters', []):
   96                  # Convert Python types to JSON Schema types
   97                  json_schema = map_python_type_to_json(param['type'])
   98                  tool['function']['parameters']['properties'][param['name']] = {
   99                      **json_schema,
  100                      "description": param.get('description', '')
  101                  }
  102                  if param.get('required', False):
  103                      tool['function']['parameters']['required'].append(param['name'])
  104  
  105              tools.append(tool)
  106          else:
  107              # Handle the case where the function is not found
  108              raise ValueError(f"Function '{func_name}' not found in the database.")
  109  
  110  
  111      # Call LiteLLM's completion API with the user message and available tools
  112>     response = litellm.completion(
  113          model="gpt-4-turbo",
  114          messages=chat_context,
  115          tools=tools,
  116          tool_choice="auto"
  117      )
  118  
  119      # Extract the message from the response
  120      response_message = response['choices'][0]['message']
```

## AG006 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:301

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L301

> LLM call (openai.chat) sets no output-token cap

```python
  277  
  278  
  279  def _translate_doc(
  280      content: str,
  281      lang: DocLang,
  282      client: OpenAI,
  283  ) -> str:
  284      """Translate an English doc to another language.
  285  
  286      Args:
  287          content: English MDX content.
  288          lang: Target language code.
  289          client: OpenAI client.
  290  
  291      Returns:
  292          Translated MDX content.
  293      """
  294      language_name = _LANGUAGE_NAMES[lang]
  295      prompt = _TRANSLATE_DOC_PROMPT.format(
  296          language=language_name,
  297          lang_code=lang,
  298          content=content,
  299      )
  300  
  301>     response = client.chat.completions.create(
  302          model="gpt-4o-mini",
  303          messages=[
  304              {
  305                  "role": "system",
  306                  "content": f"You are a professional translator. Translate technical documentation into {language_name}. Output only the translated MDX.",
  307              },
  308              {"role": "user", "content": prompt},
  309          ],
```

## AG006 crewAIInc/crewAI lib/crewai/src/crewai/utilities/internal_instructor.py:169

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/crewai/src/crewai/utilities/internal_instructor.py#L169

> LLM call (openai.chat) sets no output-token cap

```python
  145          Raises:
  146              ValueError: If LLM is not provided or invalid, or if a hook blocked
  147                  the call by returning ``False``.
  148              HookAborted: If a hook denied the call.
  149          """
  150          from crewai.llms.base_llm import BaseLLM
  151  
  152          messages: list[LLMMessage] = [{"role": "user", "content": self.content}]
  153  
  154          if not _is_valid_llm(self.llm):
  155              raise ValueError(
  156                  "LLM must be provided and have a model attribute or be a string"
  157              )
  158  
  159          if isinstance(self.llm, str):
  160              model_name = self.llm
  161          else:
  162              model_name = self.llm.model
  163  
  164          if isinstance(self.llm, BaseLLM):
  165              # This reaches the provider client directly, so the hooks the LLM
  166              # layer would have dispatched are dispatched here instead.
  167              self.llm._invoke_before_llm_call_hooks(messages, self.agent)
  168  
  169>         return self._client.chat.completions.create(  # type: ignore[no-any-return]
  170              model=model_name, response_model=self.model, messages=messages
  171          )
```

## AG006 crewAIInc/crewAI lib/devtools/src/crewai_devtools/docs_check.py:225

https://github.com/crewAIInc/crewAI/blob/6b93fa0e25a926215ca7bb52a95d4db7d9d7262d/lib/devtools/src/crewai_devtools/docs_check.py#L225

> LLM call (openai.chat) sets no output-token cap

```python
  201  
  202      Args:
  203          reason: Why this doc is needed.
  204          existing_content: Existing doc content for style reference, or None.
  205          diff_context: The code diff to document.
  206          client: OpenAI client.
  207  
  208      Returns:
  209          Generated MDX content.
  210      """
  211      context = ""
  212      if existing_content:
  213          context = f"Reference existing doc for style:\n{existing_content[:5000]}"
  214  
  215      diff_section = ""
  216      if diff_context:
  217          diff_section = f"Code changes:\n{diff_context[:10000]}"
  218  
  219      prompt = _GENERATE_DOC_PROMPT.format(
  220          reason=reason,
  221          existing_content=context,
  222          diff_context=diff_section,
  223      )
  224  
  225>     response = client.chat.completions.create(
  226          model="gpt-4o",
  227          messages=[
  228              {
  229                  "role": "system",
  230                  "content": "You are a technical writer. Output only MDX content.",
  231              },
  232              {"role": "user", "content": prompt},
  233          ],
```

## AG006 yoheinakajima/babyagi babyagi/functionz/packs/plugins/e2b.py:57

https://github.com/yoheinakajima/babyagi/blob/fa8930ebe72a82e5ad57b356e7cbec96290e5bb2/babyagi/functionz/packs/plugins/e2b.py#L57

> LLM call (litellm) sets no output-token cap

```python
   33  
   34  @babyagi.register_function(
   35      metadata={"description": "Calls the OpenAI API (gpt-3.5-turbo) to generate code and execute it in an E2B sandbox."},
   36      imports=["litellm", "os"],
   37      key_dependencies=["openai_api_key"],
   38      dependencies=["execute_code_in_sandbox"]
   39  )
   40  def chat_with_llm_and_execute(user_message: str):
   41      """
   42      This function calls the OpenAI API (via litellm) to generate Python code based on the user's message,
   43      then executes that code in an E2B sandbox.
   44  
   45      :param user_message: The message to prompt the LLM with.
   46      :return: Results from the executed code and logs.
   47      """
   48      from litellm import completion
   49    
   50      # Load OpenAI API key from environment
   51      api_key = globals()['openai_api_key']
   52  
   53      # Define the message for the LLM
   54      messages = [{"role": "user", "content": user_message}]
   55  
   56      # Call the LLM using litellm completion method
   57>     response = completion(model="gpt-3.5-turbo", messages=messages)
   58      llm_generated_code = response['choices'][0]['message']['content']
   59  
   60      # Execute the generated code in the E2B sandbox
   61      return execute_code_in_sandbox(llm_generated_code)
   62  
   63  
   64  # Function 3: Save generated charts
   65  
```
