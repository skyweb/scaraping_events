import { PageLayout } from "@/components/layout/PageLayout"
import { MainFeed } from "@/components/sections/MainFeed"
import { RightSidebar } from "@/components/sections/RightSidebar"

function App() {
  return (
    <PageLayout>
      {/* Layout libero.it: area principale con carousel orizzontali + sidebar destra.
          Su mobile la sidebar va sotto il feed. */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_280px]">
        <MainFeed />
        <RightSidebar />
      </div>
    </PageLayout>
  )
}

export default App
