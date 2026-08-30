import "./globals.css";
import { ReactNode } from "react";
export const metadata={title:"JARVIS OS",description:"JARVIS AI Operating System"};
export default function Layout({children}:{children:ReactNode}){return <html lang="en"><body>{children}</body></html>}
