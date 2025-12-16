# Insurance Claims Processing UI

Next.js 15 frontend application for the insurance multi-agent system, providing document management, claims processing, and workflow visualization.

## Features

- **Multi-Agent Dashboard**: Real-time agent status and workflow visualization
- **Claims Documents**: Upload and analyze claims with Azure Content Understanding
- **Policy Documents**: Browse, search, and view insurance policies
- **Workflow Demo**: Interactive claim processing scenarios
- **Feedback System**: Agent performance ratings and evaluations
- **Next.js 15** with App Router
- **React 19** with latest features
- **shadcn/ui** components for beautiful UI
- **Tailwind CSS v4** for styling
- **TypeScript** for type safety

## Local Development

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Troubleshooting

### React 19 Compatibility

If you encounter peer dependency errors, use the legacy peer deps flag:

```bash
npm install --legacy-peer-deps
```

This is due to some packages not yet supporting React 19.

## Environment Variables

For local development, the frontend automatically connects to `http://localhost:8000` for the backend API.

In production (Azure Container Apps), it automatically detects and connects to the deployed backend.

Required configuration in `.env.local` (optional for local dev):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000  # Backend API URL
```

## Application Structure

```
frontend/
├── app/
│   ├── agents/             # Agent detail pages
│   │   ├── claim-assessor/
│   │   ├── policy-checker/
│   │   ├── risk-analyst/
│   │   └── communication-agent/
│   ├── demo/               # Interactive workflow demo
│   ├── documents/          # Document management
│   │   ├── manage/         # Claims document upload
│   │   └── index-management/ # AI Search index management
│   ├── page.tsx            # Dashboard homepage
│   └── layout.tsx          # Root layout
├── components/
│   ├── app-sidebar.tsx     # Navigation sidebar
│   ├── agent-workflow-visualization.tsx # Workflow chart
│   ├── content-understanding-test.tsx # Document analysis UI
│   ├── workflow-demo.tsx   # Demo scenarios
│   ├── feedback/           # Agent feedback components
│   │   ├── ImmediateAgentFeedbackFormWithAPI.tsx
│   │   └── WorkflowCompletionFeedbackForm.tsx
│   └── ui/                 # shadcn/ui components
├── lib/
│   ├── api.ts              # Backend API client
│   ├── dashboard-api.ts    # Dashboard data fetching
│   └── config.ts           # Configuration
└── hooks/                  # React hooks
```

## Key Features

### Document Management

**Claims Documents** (`/documents/manage`):
- Upload claims documents for analysis
- Azure Content Understanding extracts structured data
- Real-time processing progress tracking
- View extracted fields (claim number, dates, amounts, etc.)

**Policy Documents** (`/documents`):
- Browse insurance policy documents
- Search by policy number, type, or holder name
- View policy details and coverage
- Download policy PDFs

### Multi-Agent Workflow

The dashboard shows real-time agent execution:
- Agent status cards (Idle/Analyzing/Completed)
- Workflow visualization with agent dependencies
- Activity feed with execution logs
- Token usage tracking

### Workflow Demo

Interactive scenarios demonstrate claim processing:
- Auto Accident Claim
- Home Water Damage
- Health Insurance Claim
- Travel Insurance Claim

Each scenario shows the full agent workflow with results.

### Agent Feedback

Rate agent performance immediately after execution:
- Star ratings (1-5)
- Structured feedback (accuracy, speed, communication)
- Free-form comments
- Feedback stored for evaluation

## Troubleshooting

### React 19 Compatibility

If you encounter peer dependency errors, use the legacy peer deps flag:

```bash
npm install --legacy-peer-deps
```

This is due to some packages not yet supporting React 19.

### Content Understanding Not Configured

If document upload shows "Content Understanding service is not configured":

1. Verify backend has `AZURE_CONTENT_UNDERSTANDING_ENDPOINT` and `AZURE_CONTENT_UNDERSTANDING_KEY` in `.env`
2. Check backend logs for Content Understanding initialization errors
3. Ensure the Azure Content Understanding resource is deployed and accessible

### Navigation Issues

If clicking between tabs doesn't work:
- Check browser console for React errors
- Ensure no "Maximum update depth exceeded" errors
- Clear browser cache and reload

## Adding shadcn/ui Components

```bash
npx shadcn@latest add button
npx shadcn@latest add button card dialog
```

## Deployment

This frontend deploys to Azure Container Apps alongside the FastAPI backend:

```bash
azd auth login
azd up
```

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
