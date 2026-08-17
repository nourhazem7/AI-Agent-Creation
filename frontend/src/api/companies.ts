import { apiClient } from "./client";
import type { CompanyMember } from "../types";

export async function listCompanyMembers(): Promise<CompanyMember[]> {
  const { data } = await apiClient.get<CompanyMember[]>("/companies/members");
  return data;
}
