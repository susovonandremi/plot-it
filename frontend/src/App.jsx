import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn } from '@clerk/clerk-react';
import Home from './pages/Home';

function App() {
     return (
          <Routes>
               <Route path="/" element={
                    <>
                         <SignedIn>
                              <Home />
                         </SignedIn>
                         <SignedOut>
                              <div className="h-screen w-screen flex items-center justify-center bg-[#0d0f12]">
                                   <SignIn routing="hash" />
                              </div>
                         </SignedOut>
                    </>
               } />
          </Routes>
     );
}

export default App;
