import { Link, Route, Routes, useLocation } from "react-router-dom";
import LandingPage from "@/pages/LandingPage";
import DateRangePage from "@/pages/DateRangePage";
import MealsResultPage from "@/pages/MealsResultPage";
import MealAnalysisPage from "@/pages/MealAnalysisPage";

export default function App() {
  const { pathname } = useLocation();
  const analysisActive = pathname === "/analysis";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b bg-[var(--color-background)]/95 backdrop-blur">
        <nav
          aria-label="주요 기능"
          className="mx-auto flex max-w-4xl px-6"
        >
          <Link
            to="/"
            aria-current={!analysisActive ? "page" : undefined}
            className={`border-b-2 px-4 py-4 text-sm font-semibold transition-colors ${
              !analysisActive
                ? "border-[var(--color-foreground)] text-[var(--color-foreground)]"
                : "border-transparent text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            }`}
          >
            학교 급식 조회
          </Link>
          <Link
            to="/analysis"
            aria-current={analysisActive ? "page" : undefined}
            className={`border-b-2 px-4 py-4 text-sm font-semibold transition-colors ${
              analysisActive
                ? "border-[var(--color-foreground)] text-[var(--color-foreground)]"
                : "border-transparent text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            }`}
          >
            학교 급식 분석
          </Link>
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/school/:schoolCode" element={<DateRangePage />} />
          <Route
            path="/school/:schoolCode/meals"
            element={<MealsResultPage />}
          />
          <Route path="/analysis" element={<MealAnalysisPage />} />
        </Routes>
      </main>
    </div>
  );
}
