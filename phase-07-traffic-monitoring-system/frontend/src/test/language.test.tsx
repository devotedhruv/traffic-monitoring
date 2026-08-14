import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { LanguageProvider } from "../app/LanguageContext";
import { LanguageToggle } from "../components/ui/LanguageToggle";

describe("interface language", () => {
  beforeEach(() => window.localStorage.clear());

  it("switches between English and Nepali and persists the choice", async () => {
    render(<LanguageProvider><LanguageToggle /><p>Dashboard</p><input placeholder="Search settings" /></LanguageProvider>);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Switch language to Nepali" }));

    await waitFor(() => expect(screen.getByText("ड्यासबोर्ड")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("सेटिङहरू खोज्नुहोस्")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("ne");
    expect(window.localStorage.getItem("trafficops-language")).toBe("ne");

    fireEvent.click(screen.getByRole("button", { name: "भाषा अङ्ग्रेजीमा बदल्नुहोस्" }));
    await waitFor(() => expect(screen.getByText("Dashboard")).toBeInTheDocument());
    expect(document.documentElement.lang).toBe("en");
  });
});
