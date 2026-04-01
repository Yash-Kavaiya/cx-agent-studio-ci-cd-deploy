```markdown
# cx-agent-studio-ci-cd-deploy Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you how to contribute to the `cx-agent-studio-ci-cd-deploy` Python codebase, focusing on its CI/CD automation, API contract alignment, and agent export/import features. You'll learn the project's coding conventions, workflow automation steps, and how to use suggested commands for common maintenance and feature tasks.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for Python files.  
  _Example:_  
  ```
  src/agent_manager.py
  configs/environments/dev.yaml
  ```

- **Import Style:**  
  Use **relative imports** within the codebase.  
  _Example:_  
  ```python
  from .evaluation import evaluate_agent
  from .agent_manager import AgentManager
  ```

- **Export Style:**  
  Use **named exports** (explicitly define what is exported).  
  _Example:_  
  ```python
  class AgentManager:
      # ...
  
  def export_agent(...):
      # ...
  ```

- **Commit Message Patterns:**  
  - Prefix with `fix` or `ci` (e.g., `fix: handle missing region flag`)
  - Average commit message length: ~58 characters

## Workflows

### Align API Contract and Endpoints
**Trigger:** When the CES API contract changes or needs to be precisely matched  
**Command:** `/align-api-contract`

1. **Update API logic:**  
   Edit `src/agent_manager.py` to match new/changed API fields, endpoints, and long-running operation (LRO) handling.
   ```python
   # Example: Update endpoint URL or request schema
   response = requests.post(
       f"{base_url}/v2/agents/export",
       json={"projectId": project_id, "appId": app_id}
   )
   ```
2. **Update evaluation logic:**  
   Edit `src/evaluation.py` for new payload/request/response schemas.
3. **Update CLI:**  
   Edit `src/cli.py` if CLI commands or options change.
4. **Update environment configs:**  
   Edit YAML files in `configs/environments/` if project IDs, app IDs, or regions change.
5. **Update workflow YAMLs:**  
   Edit `.github/workflows/*.yml` for new CLI flags or region defaults.

**Files involved:**  
- `src/agent_manager.py`
- `src/evaluation.py`
- `src/cli.py`
- `configs/environments/dev.yaml`
- `configs/environments/production.yaml`
- `configs/environments/staging.yaml`
- `.github/workflows/agent-evaluation.yml`
- `.github/workflows/cd-production.yml`
- `.github/workflows/cd-staging.yml`

---

### CI/CD Workflow Update
**Trigger:** When deployment or evaluation automation needs to be fixed or improved  
**Command:** `/update-ci-cd-workflow`

1. **Edit workflow YAMLs:**  
   Update `.github/workflows/*.yml` to change steps, flags, or triggers.
   ```yaml
   # Example: Add region flag to deployment
   - name: Deploy to GCP
     run: python src/cli.py deploy --region ${{ secrets.REGION }}
   ```
2. **Edit deployment scripts:**  
   Update shell scripts in `scripts/*.sh` as needed.
3. **Update CLI support:**  
   Optionally update `src/cli.py` or related Python files to support new CLI flags or behaviors.
4. **Test changes:**  
   Validate workflow changes by pushing to a branch or submitting a PR.

**Files involved:**  
- `.github/workflows/agent-evaluation.yml`
- `.github/workflows/cd-production.yml`
- `.github/workflows/cd-staging.yml`
- `.github/workflows/ci.yml`
- `scripts/setup_gcp.sh`
- `src/cli.py`

---

### Add or Fix Export/Import Agent Features
**Trigger:** When adding new export/import capabilities or fixing related bugs  
**Command:** `/add-export-import-feature`

1. **Update agent logic:**  
   Edit `src/agent_manager.py` to implement or fix export/import logic and ensure API contract alignment.
   ```python
   def export_agent(agent_id, output_path):
       # Implement export logic here
       pass
   ```
2. **Update CLI:**  
   Edit `src/cli.py` to expose new CLI options or commands.
   ```python
   @cli.command()
   def export(agent_id: str, output: str):
       export_agent(agent_id, output)
   ```
3. **Update or add tests:**  
   Edit or add tests in `tests/test_agent_manager.py`.
   ```python
   def test_export_agent(tmp_path):
       # Test export logic
       ...
   ```
4. **Update workflows:**  
   Edit `.github/workflows/cd-production.yml` if deployment/export logic changes.
5. **Update evaluation logic:**  
   Optionally update `src/evaluation.py` for related logic.

**Files involved:**  
- `src/agent_manager.py`
- `src/cli.py`
- `src/evaluation.py`
- `tests/test_agent_manager.py`
- `.github/workflows/cd-production.yml`

---

## Testing Patterns

- **Framework:** Unknown (no explicit framework detected)
- **Test File Pattern:**  
  Test files are named with the pattern `tests/test_*.py` for Python tests.
- **Example Test:**  
  ```python
  def test_export_agent(tmp_path):
      # Arrange
      # Act
      # Assert
      ...
  ```

## Commands

| Command                   | Purpose                                                      |
|---------------------------|--------------------------------------------------------------|
| /align-api-contract       | Align codebase with latest CES API contract and endpoints    |
| /update-ci-cd-workflow    | Update CI/CD pipeline workflows and related scripts          |
| /add-export-import-feature| Implement or fix agent export/import features                |
```
