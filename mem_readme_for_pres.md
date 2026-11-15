The current code combines **thread-scoped working memory in LangGraph** with **durable conversation history in PostgreSQL**. The backend supplies remembered information to the LLM as part of its input.

No code was changed.

One terminology detail matters: a **run** is one call to `app_graph.ainvoke(...)`, while a **thread** can contain several runs. Your short-term memory therefore supports both communication between nodes within a run and continuity between requests that reuse the same thread.

| Memory | Storage | Identifier | How it is used |
|---|---|---|---|
| Short-term conversation and task state | LangGraph state, checkpointed in backend RAM | `thread_id` | Automatically available when continuing the same thread |
| Long-term conversation history | PostgreSQL message and session tables | `user_id`, through session ownership | Retrieved when the tutor requests the history tool |
| Persistent learning statistics and goals | PostgreSQL user tables | `user_id` | Loaded into application state on each request |

1. **The request identifies the current conversation and the user.**

   `ChatRequest` accepts `user_id`, `prompt`, and an optional `thread_id`. In `chat()`, the backend reuses the supplied thread ID or generates a UUID:

   ```python
   session_id = request.thread_id or str(uuid.uuid4())
   config = {"configurable": {"thread_id": session_id}}
   ```

   This configuration tells LangGraph which thread’s checkpoint to use. The route then invokes the graph with that configuration. See [routes.py, lines 23–26](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:23>), [lines 54–55](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:54>), and [line 78](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:78>).

   The two identifiers have different purposes:

   - `thread_id` selects the current conversation’s working state.
   - `user_id` selects saved information associated with the user, potentially spanning several threads.

   In the frontend, `threadId` is held in React state, sent with each request, and updated from the backend’s response. That is how successive questions and quiz answers continue the same conversation. See [page.tsx, lines 30–41](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/frontend/app/page.tsx:30>) and [lines 78–79](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/frontend/app/page.tsx:78>).

2. **`AgentState` holds the short-term conversation and the current task state.**

   The central definition is:

   ```python
   messages: Annotated[list[BaseMessage], add_messages]
   ```

   The `add_messages` reducer merges incoming messages into the existing conversation. New messages are normally appended; a message with an existing message ID replaces that message. Consequently, a node can return only its newly generated message without replacing the whole conversation. See [state.py, lines 25–35](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/state.py:25>).

   The route supplies only the latest user message:

   ```python
   "messages": [HumanMessage(content=request.prompt)]
   ```

   LangGraph merges it with the messages already associated with the thread. The frontend therefore does not need to resend the conversation transcript. See [routes.py, lines 67–75](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:67>).

   Other state fields retain the current task’s information, including:

   - `awaiting_eval`: whether the execution should evaluate an answer.
   - `options_list`: answer choices, correctness flags, and explanations.
   - `current_probe_id`: the database identifier of the current question.
   - `user_stats`: the user’s learning statistics.
   - `user_goals`: goals loaded from the user profile.

   These fields do not have the message reducer. They hold current values that nodes or new request inputs can overwrite.

   The state is retained through:

   ```python
   checkpointer = InMemorySaver()
   app_graph = workflow.compile(checkpointer=checkpointer)
   ```

   This preserves checkpoints in the running backend process and allows a later invocation with the same `thread_id` to continue from its previous state. See [graph.py, lines 278–279](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:278>).

3. **Each graph node uses a different portion of that short-term memory.**

   The graph follows either `tutor → prober → END` or `evaluate → END`. Its entry routing checks `awaiting_eval`; the API sets that value according to whether the submitted prompt starts with `/a`. See [graph.py, lines 256–276](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:256>) and [routes.py, lines 57–69](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:57>).

   **The tutor receives the accumulated conversation.** It builds its input using:

   ```python
   full_messages = [system_prompt] + list(state["messages"])
   ```

   This gives it the current question alongside earlier user questions, tutor explanations, probe questions, submitted answers, and evaluation feedback in the thread. It can therefore interpret references such as “explain that example again.” See [graph.py, lines 81–84](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:81>).

   The tutor returns its final response as `"messages": [response]`. The reducer adds that response to the conversation, making it available to subsequent nodes and runs. See [graph.py, lines 116–123](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:116>).

   **The prober receives only the latest tutor explanation.** Its input is:

   ```python
   full_messages = [system_prompt, state["messages"][-1]]
   ```

   Because the tutor has just appended its response, this last message is the explanation the prober should test. The prober does not independently receive the entire conversation or retrieve database history. Earlier context can influence its question indirectly through the tutor’s explanation. See [graph.py, lines 125–133](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:125>).

   **The evaluator uses retained task state.** The prober stores its generated options and probe ID in `options_list` and `current_probe_id`. On a subsequent answer submission, the evaluator reads those options to identify the correct selections. This evaluation uses Python comparisons rather than an LLM call. See [graph.py, lines 166–172](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:166>) and [lines 174–195](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:174>).

   After evaluation, the feedback is appended to `messages`, while `awaiting_eval` becomes false and `options_list` is cleared. The tutor can subsequently see that feedback as part of the conversation. See [graph.py, lines 247–253](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:247>).

4. **Completed exchanges are saved to PostgreSQL for long-term recall.**

   The database schema separates sessions from messages:

   - `chat_sessions` associates each `thread_id` with a `user_id`.
   - `chat_messages` stores each message’s thread, sequence number, role, content, originating node, and creation time.

   This relationship allows the backend to find messages from several conversations belonging to the same user. See [001_initialmigration.sql, lines 10–27](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/migrations/001_initialmigration.sql:10>).

   Before graph execution, the route ensures that the session exists in the database. See [routes.py, line 64](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:64>) and [database.py, lines 150–162](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/db/database.py:150>).

   After execution, the route saves:

   | Request type | Newly saved messages |
   |---|---|
   | Tutor question | Human prompt, tutor explanation, prober question |
   | `/a` answer | Human answer, evaluation feedback |

   The route takes the last three or two graph messages respectively and assigns sequence numbers based on their positions in the accumulated conversation. Each write is awaited before the HTTP response returns, so the next completed request can retrieve the exchange. See [routes.py, lines 90–100](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:90>).

   `record_message()` performs the SQL insertion and commits it. The saved messages therefore exist independently of the backend’s in-memory checkpoints. See [database.py, lines 164–179](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/db/database.py:164>). The Docker configuration also places PostgreSQL’s data directory in the named `pgdata` volume. See [docker-compose.yml, lines 11–15](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/docker-compose.yml:11>).

5. **The tutor can request long-term history through the `@tool` function.**

   Inside `tutor_node`, this declaration creates a tool available to the model:

   ```python
   @tool
   async def get_chat_history(limit: int = 20) -> list[dict] | str:
   ```

   The decorator gives LangChain a tool definition derived from the function’s name, description, and arguments. Defining the tool does not immediately query the database. See [graph.py, lines 85–97](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:85>).

   The model can supply `limit`, but the backend supplies the user identity through the surrounding state:

   ```python
   return await a_get_chat_history(state["user_id"], limit)
   ```

   Thus, the tool’s user scope comes from the current request’s state rather than an argument chosen by the model.

   The system prompt instructs the tutor to request history when earlier conversations or explanations are missing from its current context. It also tells the model to treat retrieved messages as historical context and avoid inventing unavailable history. See [graph.py, lines 99–104](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:99>).

   The execution then proceeds through two possible paths:

   ```python
   response = await llm.bind_tools([get_chat_history]).ainvoke(full_messages)
   ```

   If the model answers directly, that response becomes the tutor explanation. If it returns tool calls, the backend:

   - Appends the model’s tool-call message to `full_messages`.
   - Executes each requested call with `get_chat_history.ainvoke(tool_call)`.
   - Appends the resulting tool response.
   - Calls the LLM again with the expanded context to obtain the final explanation.

   See [graph.py, lines 105–113](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:105>).

   The actual database access is performed by Python. The LLM requests the function and then reads its result. This is an internal function-call path; the implementation does not introduce a separate HTTP history endpoint.

   The code permits one tool-call round, potentially containing several calls. Its final LLM invocation uses `llm.ainvoke(...)` without binding the tool again.

6. **The database lookup retrieves a recent window of the user’s messages.**

   `get_chat_history()` joins `chat_messages` to `chat_sessions` and filters using:

   ```sql
   WHERE s.user_id = %s AND m.role IN ('human', 'ai')
   ```

   Its result includes `thread_id`, `sequence_no`, `role`, `content`, and `node_name`. See [database.py, lines 181–198](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/db/database.py:181>).

   The query’s behaviour is:

   - It covers all sessions associated with that user, including the current thread’s already saved messages.
   - It defaults to 20 messages and clamps the requested limit to between 1 and 50.
   - It selects the newest messages using creation time and ID.
   - It reverses the selected rows before returning them, so the retrieved window reads oldest first.

   Recall is therefore based on **recent messages**, rather than searching for a particular concept or topic. A relevant explanation outside that recent window will not be returned.

   The async adapter uses `asyncio.to_thread()` to run the synchronous PostgreSQL operation outside FastAPI’s event loop. See [database.py, lines 293–294](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/db/database.py:293>).

   If retrieval fails, the tool returns “Conversation history is temporarily unavailable.” The tutor can then respond with that limitation in context. See [graph.py, lines 93–103](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:93>).

   **The retrieved tool messages remain local to that tutor invocation.** Only the final tutor explanation is returned into `AgentState.messages`. Future turns retain whatever the tutor included in its explanation, while the raw retrieved rows require another lookup if needed. See [graph.py, lines 107–117](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:107>).

7. **Other persistent data supports the application, with a narrower connection to LLM context.**

   Before each graph invocation, the route reloads the user’s profile, statistics, and goals from PostgreSQL and places them in graph state. See [routes.py, lines 60–75](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:60>).

   Evaluation updates the statistics and persists them through `a_upsert_user_stats()`. This allows streaks and scores to continue across conversations and backend restarts. See [graph.py, lines 225–235](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:225>).

   However, having a field in graph state does not automatically expose it to the LLM. The tutor receives `state["messages"]`; the prober receives the latest tutor message. Their inputs currently omit the separate `user_stats` and `user_goals` fields.

   Questions, answer metadata, and lifecycle events also have separate persistence paths. The history tool reads conversational messages rather than those tables directly. Probe persistence occurs at [graph.py, lines 161–163](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:161>); answer and event persistence use background tasks at [lines 234–244](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:234>) and [lines 64–79](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:64>).

The current design has several practical boundaries:

- **A backend restart clears short-term checkpoints.** PostgreSQL history remains retrievable, but the code does not rebuild the complete `AgentState` from it. In particular, pending quiz options and probe IDs are not reloaded, so a pending quiz cannot reliably resume after a restart.
- **Reusing an old thread after a restart has a logging edge case.** Sequence numbers are calculated from the restarted in-memory message list, while `record_message()` ignores existing `(thread_id, sequence_no)` conflicts. New exchanges can therefore collide with old rows. The relevant code is [routes.py, lines 92–99](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/api/routes.py:92>) and [database.py, lines 169–172](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/db/database.py:169>).
- **A frontend reload normally starts a new thread.** The thread ID and displayed messages are held in React state. The current frontend also uses the fixed identity `default_user`, so its database recall uses that shared identity. See [page.tsx, lines 22–42](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/frontend/app/page.tsx:22>).
- **The accumulated thread transcript has no explicit trimming or summarisation.** The tutor input includes the complete current `messages` list at [graph.py, line 84](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/graph.py:84>), so that context grows as the thread continues.
- **The complete message-saving path belongs to `/api/chat`.** The CLI script invokes the graph directly, bypassing the route’s transcript logging. It can use thread memory and retrieve existing history, but its exchanges do not pass through that message-saving loop. See [test.py, lines 57–64](<C:/Users/bluey/OneDrive - National University of Singapore/Documents/Year 4 (AY2026-27)/fyp/fyp_project_1/backend/src/test.py:57>).
- **Earlier tutor explanations omitted by the previous logger remain unavailable.** Retrieval can return only messages that were actually saved.