# Counterfactual Financial Oracle

An interactive, multi-agent AI system for counterfactual financial analysis.

## Features
- **Landing AI Ingestion**: Extracts financial data from PDFs (Mocked for demo).
- **OpenAI Simulation**: Runs Monte Carlo simulations with `gpt-5-nano` providing qualitative insights.
- **DeepSeek Critic**: Adversarially critiques the simulation results.
- **ChatGPT Evaluator**: Synthesizes findings and generates a PDF report.
- **Streamlit Interface**: Interactive dashboard for scenario planning.

## Setup
1. Install dependencies:
   ```bash
   pip install -r counterfactual_oracle/requirements.txt
   ```
2. Run the app:
   ```bash
   streamlit run counterfactual_oracle/app.py
   ```

## Architecture
- `src/models.py`: Pydantic data models.
- `src/logic.py`: Core financial formulas and Monte Carlo engine.
- `src/agents/`: AI agent wrappers.
- `tests/`: Unit tests for logic.

## Usage
1. Upload a PDF (any PDF will trigger the mock extraction for this demo).
2. Adjust the sliders to set counterfactual scenarios (e.g., increase OpEx).
3. Click "Run Simulation".
4. View the debate between the Simulator and Critic.
5. Download the final PDF report.
