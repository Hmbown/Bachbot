import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { Home } from './pages/Home';
import { CorpusExplorer } from './pages/CorpusExplorer';
import { ChoraleDetail } from './pages/ChoraleDetail';
import { ChoraleComparison } from './pages/ChoraleComparison';
import { CompositionWorkshop } from './pages/CompositionWorkshop';
import { TheoryClassroom } from './pages/TheoryClassroom';
import { ResearchLab } from './pages/ResearchLab';
import { BenchmarkArena } from './pages/BenchmarkArena';
import { HumanEvaluation } from './pages/HumanEvaluation';
import { Encyclopedia, EncyclopediaArticle } from './pages/Encyclopedia';
import { ApiPlayground } from './pages/ApiPlayground';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/corpus" element={<CorpusExplorer />} />
            <Route path="/corpus/compare" element={<ChoraleComparison />} />
            <Route path="/corpus/:choraleId" element={<ChoraleDetail />} />
            <Route path="/compose" element={<CompositionWorkshop />} />
            <Route path="/theory" element={<TheoryClassroom />} />
            <Route path="/research" element={<ResearchLab />} />
            <Route path="/benchmark" element={<BenchmarkArena />} />
            <Route path="/benchmark/evaluate" element={<HumanEvaluation />} />
            <Route path="/encyclopedia" element={<Encyclopedia />} />
            <Route path="/encyclopedia/:slug" element={<EncyclopediaArticle />} />
            <Route path="/api-docs" element={<ApiPlayground />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
